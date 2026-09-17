import datetime
from unittest.mock import MagicMock

import pytest
from aliceio import Skill
from aliceio.enums.update import RequestType
from aliceio.types import (
    AliceRequest,
    Application,
    Interfaces,
    Meta,
    Session,
    Update,
    User,
)

from alice_skill.cache import HomeworkCache
from alice_skill.config import Config, SgoConfig
from alice_skill.handlers.common import ERROR_TEXT, TIMEOUT_TEXT
from alice_skill.sgo import HomeworkResult
from alice_skill.skill import create_app
from alice_skill.worker import PrefetchWorker


def _make_update(command: str = "", *, session_new: bool = False) -> Update:
    user = User(user_id="test-user")
    app = Application(application_id="test-app")
    session = Session(
        message_id=1,
        session_id="test-sid",
        skill_id="test-skill",
        application=app,
        new=session_new,
        user=user,
    )
    request = AliceRequest(
        type=RequestType.SIMPLE_UTTERANCE,
        command=command,
        original_utterance=command,
    )
    meta = Meta(
        locale="ru-RU",
        timezone="Europe/Moscow",
        client_id="test",
        interfaces=Interfaces(),
    )
    return Update(meta=meta, session=session, request=request, version="1.0")


def _make_config(skill_id: str = "test-skill") -> Config:
    return Config(
        sgo=SgoConfig(login="u", password="p", school="s"),
        skill_id=skill_id,
    )


def _fill_cache(dp, cache, worker):
    dp.workflow_data["cache"] = cache
    dp.workflow_data["worker"] = worker


_free_app_state: list = []


def _free_app(make_config, *, cache=None, worker=None):
    # aliceio routers can be attached to only one Dispatcher per process,
    # so reuse a single app/dispatcher and swap per-test cache/worker via
    # workflow_data.
    if not _free_app_state:
        _free_app_state.append(create_app(make_config()))
    app = _free_app_state[0]
    dp = app["dispatcher"]
    _fill_cache(dp, cache or HomeworkCache(), worker or MagicMock(spec=PrefetchWorker))
    return app, dp


@pytest.mark.asyncio
async def test_timeout_handler_registered():
    app, dp = _free_app(_make_config)
    skill = Skill(skill_id="test-skill")
    # The timeout handler is registered on dp.timeout and returns the phrase.
    handler = dp.timeout.handlers[0]
    assert await handler.callback(object()) == TIMEOUT_TEXT


@pytest.mark.asyncio
async def test_error_handler_registered():
    app, dp = _free_app(_make_config)
    handler = dp.errors.handlers[0]
    assert await handler.callback(object()) == ERROR_TEXT


@pytest.mark.asyncio
async def test_router_order_homework_reaches_homework_handler():
    cache = HomeworkCache()
    cache.set(HomeworkResult(
        status="ok",
        target_date=datetime.date(2026, 9, 21),
        text="На завтра одно задание.",
    ))
    worker = MagicMock(spec=PrefetchWorker)
    app, dp = _free_app(_make_config, cache=cache, worker=worker)

    skill = Skill(skill_id="test-skill")
    update = _make_update("что задали")
    resp = await dp.feed_webhook_update(skill, update)
    assert resp is not None
    assert "одно задание" in resp.response.text
    worker.refresh_now.assert_not_called()


@pytest.mark.asyncio
async def test_router_order_more_returns_cached():
    cache = HomeworkCache()
    cache.set(HomeworkResult(
        status="ok",
        target_date=datetime.date(2026, 9, 21),
        text="Догруженный текст.",
    ))
    worker = MagicMock(spec=PrefetchWorker)
    app, dp = _free_app(_make_config, cache=cache, worker=worker)

    skill = Skill(skill_id="test-skill")
    update = _make_update("дальше")
    resp = await dp.feed_webhook_update(skill, update)
    assert resp is not None
    assert resp.response.text == "Догруженный текст."


@pytest.mark.asyncio
async def test_router_order_fallback():
    cache = HomeworkCache()
    worker = MagicMock(spec=PrefetchWorker)
    app, dp = _free_app(_make_config, cache=cache, worker=worker)

    skill = Skill(skill_id="test-skill")
    update = _make_update("привет")
    resp = await dp.feed_webhook_update(skill, update)
    assert resp is not None
    assert "Я умею рассказывать домашку" in resp.response.text


@pytest.mark.asyncio
async def test_router_order_session_new():
    cache = HomeworkCache()
    cache.set(HomeworkResult(
        status="ok",
        target_date=datetime.date(2026, 9, 21),
        text="На завтра три задания.",
    ))
    worker = MagicMock(spec=PrefetchWorker)
    app, dp = _free_app(_make_config, cache=cache, worker=worker)

    skill = Skill(skill_id="test-skill")
    update = _make_update("включи навык", session_new=True)
    resp = await dp.feed_webhook_update(skill, update)
    assert resp is not None
    assert "три задания" in resp.response.text