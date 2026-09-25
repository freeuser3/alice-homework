from __future__ import annotations

import asyncio
import datetime
import logging

from aliceio import F, Router
from aliceio.types import Message, Response

from alice_skill.quiz_state import SummarySlot
from alice_skill.homework import summarize_context

from .common import ERROR_TEXT, PREMATURE_TEXT

logger = logging.getLogger(__name__)

summary_router = Router(name="summary")

SUMMARY_FILTER = (
    F.command.contains("итог")
    | F.command.contains("успеваемост")
    | F.command.contains("прошла неделя")
    | F.command.contains("как дела в школе")
)

DIRECT_TIMEOUT = 3.5

SUMMARY_NOT_CONFIGURED_TEXT = "Итоги не настроены. Попроси взрослых включить функцию."
PREMATURE_SUMMARY_TEXT = "Секунду, собираю итог недели. Скажи «дальше»."
PREMATURE_SUMMARY_MORE_TEXT = "Ещё чуть-чуть, собираю итог. Скажи «дальше» ещё раз."
SUMMARY_FAIL_TEXT = "Не получилось собрать итог. Попробуй ещё раз."

SYSTEM_PROMPT = (
    "Ты — школьный наставник. По данным о неделе дай короткий (не больше 3-4 "
    "предложений) доброжелательный голосовой итог: что хорошо, что подтянуть, "
    "какие долги и что на завтра. Отвечай только сообщением, без пояснений и "
    "эмодзи."
)


def _summary_task(llm, context: str, slot: SummarySlot) -> asyncio.Task:
    async def run() -> None:
        try:
            text = await llm.complete(SYSTEM_PROMPT, context)
        except Exception:
            logger.exception("summary generation failed")
            text = None
        slot.finish(text)

    return asyncio.create_task(run())


@summary_router.message(SUMMARY_FILTER)
async def handle_summary(message: Message, cache, worker, quiz, summary_slot, today: datetime.date | None = None) -> Response:
    if quiz is None or quiz.llm is None:
        return Response(text=SUMMARY_NOT_CONFIGURED_TEXT)

    result = cache.get()
    if result is None or result.status == "error":
        worker.refresh_now()
        return Response(text=PREMATURE_TEXT)
    if result.status != "empty" and result.target_date is None:
        worker.refresh_now()
        return Response(text=PREMATURE_TEXT)

    today = today or datetime.date.today()
    target = result.target_date or today + datetime.timedelta(days=1)
    homework = [
        (entry.subject, entry.content) for entry in result.entries
    ]
    context = summarize_context(
        result.week_schedule,
        result.week_marks,
        result.overdue,
        result.lessons,
        homework,
        target,
        today,
    )

    slot = summary_slot
    if slot.has_pending and slot.task is not None and not slot.task.done():
        return Response(text=PREMATURE_SUMMARY_MORE_TEXT)
    if slot.text is not None:
        text = slot.text
        slot.clear()
        return Response(text=text)

    task = _summary_task(quiz.llm, context, slot)
    slot.set_pending(task)

    done, _ = await asyncio.wait({task}, timeout=DIRECT_TIMEOUT)
    if task in done:
        if slot.text is not None:
            text = slot.text
            slot.clear()
            logger.info("summary: generated")
            return Response(text=text)
        slot.clear()
        logger.info("summary: generation failed")
        return Response(text=SUMMARY_FAIL_TEXT)
    logger.info("summary: direct timeout, answer later")
    return Response(text=PREMATURE_SUMMARY_TEXT)