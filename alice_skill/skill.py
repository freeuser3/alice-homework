from __future__ import annotations

import logging

import aiohttp.web as web
from aliceio import Dispatcher, Skill
from aliceio.webhook.aiohttp_server import (
    OneSkillAiohttpRequestHandler,
    setup_application,
)

from alice_skill.cache import HomeworkCache
from alice_skill.config import Config, load_config
from alice_skill.handlers.common import ERROR_TEXT, TIMEOUT_TEXT
from alice_skill.handlers.fallback import fallback_router
from alice_skill.handlers.grades import grades_router
from alice_skill.handlers.help import help_router
from alice_skill.handlers.homework import homework_router
from alice_skill.handlers.more import more_router
from alice_skill.handlers.quiz import quiz_router
from alice_skill.handlers.start import start_router
from alice_skill.handlers.timetable import timetable_router
from alice_skill.logging_middleware import LoggingMiddleware
from alice_skill.logging_setup import setup_logging
from alice_skill.quiz_service import build_quiz
from alice_skill.quiz_state import QuizSlot
from alice_skill.sgo import fetch_homework
from alice_skill.worker import PrefetchWorker

logger = logging.getLogger(__name__)


def create_app(config: Config) -> web.Application:
    cache = HomeworkCache()
    worker = PrefetchWorker(
        fetch=lambda: fetch_homework(
            config.sgo.login, config.sgo.password, config.sgo.school,
        ),
        cache=cache,
        interval=config.prefetch_interval,
    )

    quiz = build_quiz(config)
    slot = QuizSlot()

    dp = Dispatcher(
        response_timeout=4.0,
        cache=cache,
        worker=worker,
        quiz=quiz,
        slot=slot,
    )
    dp.update.middleware(LoggingMiddleware())

    # Router order matters: start → homework → quiz → more → fallback
    dp.include_router(start_router)
    dp.include_router(homework_router)
    dp.include_router(quiz_router)
    dp.include_router(more_router)
    dp.include_router(timetable_router)
    dp.include_router(grades_router)
    dp.include_router(help_router)
    dp.include_router(fallback_router)

    @dp.startup()
    async def on_startup() -> None:
        logger.info("starting prefetch worker")
        await worker.start()

    @dp.shutdown()
    async def on_shutdown() -> None:
        logger.info("stopping prefetch worker")
        await worker.stop()
        if quiz is not None:
            await quiz.close()

    @dp.timeout()
    async def on_timeout(event) -> str:
        logger.warning("timeout processing update")
        return TIMEOUT_TEXT

    @dp.errors()
    async def on_error(event) -> str:
        logger.exception("unhandled error in handler")
        return ERROR_TEXT

    skill = Skill(skill_id=config.skill_id)
    request_handler = OneSkillAiohttpRequestHandler(dispatcher=dp, skill=skill)

    app = web.Application()
    request_handler.register(app, path="/alice")
    setup_application(app, dp, skill=skill)
    app["dispatcher"] = dp  # expose for tests
    return app


def main() -> None:
    config = load_config()
    setup_logging(config.log_path)
    app = create_app(config)
    web.run_app(app, host=config.host, port=config.port)


if __name__ == "__main__":
    main()