from __future__ import annotations

import asyncio
import datetime
import logging

from aliceio import F, Router
from aliceio.types import Message, Response

from alice_skill.homework import collect_week_facts, summarize_context
from alice_skill.memory_store import SummaryMemory
from alice_skill.quiz_state import SummarySlot

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

SYSTEM_PROMPT = """Ты — строгий и спокойный школьный наставник.

Ученик — мальчик. Всегда используй мужской род.

Твой ответ будет автоматически передан на умную колонку с голосовым помощником
Алиса и полностью озвучен вслух. Поэтому пиши не письменный отчёт, а короткую
естественную речь, которую приятно слушать.

4–5 коротких предложений, до 70 слов.

Скажи: общий итог недели; что получилось или не получилось с конкретными
цифрами и предметами; долги и задания на следующий учебный день,
указывая его день недели и дату; что важно исправить дальше.

Используй только факты из данных. Не выдумывай причины, прогресс или ухудшение.
Не повторяй одну мысль и не сравнивай с другими учениками.

Ученик любит шахматы, поэтому иногда используй одну короткую естественную
шахматную метафору, связанную с итогом недели. Не вставляй её ради метафоры
и не используй больше одной за отчёт. Не повторяй один образ в двух отчётах подряд.

Для озвучивания Алиcой используй короткие простые предложения и естественный
разговорный русский. Не используй списки, заголовки, скобки, эмодзи,
канцелярит и длинные перечисления.

Верни только текст, который должен произнести голосовой помощник Алиса.
"""

DIGEST_PROMPT = (
    "Ты сжимаешь месяцы наблюдений школьного наставника в краткую память. "
    "Прочитай недели ниже и сформулируй 2-3 предложения: общая динамика "
    "ученика (что улучшилось, что ухудшилось), слабые и сильные предметы, "
    "проблемы с долгами. Никакой похвалы и воды — только факты и цифры. "
    "Отвечай только текстом памяти."
)

_fold_tasks: set[asyncio.Task] = set()

SUMMARY_RETRIES = 3
SUMMARY_RETRY_DELAY = 0.5
TRANSIENT_MARKERS = ("HTTP 5", "all_providers_failed",
                     "Service temporarily unavailable")


def _is_transient_error(exc: Exception) -> bool:
    msg = str(exc)
    return any(marker in msg for marker in TRANSIENT_MARKERS)


async def _complete_with_retry(llm, system: str, user: str) -> str:
    """Пытается выполнить запрос, ретрая транзиентные сбои (5xx/timeout)."""
    last: Exception | None = None
    for attempt in range(SUMMARY_RETRIES):
        try:
            return await llm.complete(system, user)
        except Exception as exc:
            last = exc
            if not _is_transient_error(exc):
                raise
            logger.warning("summary llm transient error (attempt %d/%d): %s",
                           attempt + 1, SUMMARY_RETRIES, exc)
            if attempt < SUMMARY_RETRIES - 1:
                await asyncio.sleep(SUMMARY_RETRY_DELAY)
    assert last is not None
    raise last


def _summary_task(llm, fallback_llm, context: str, slot: SummarySlot,
                  memory: SummaryMemory | None, week: str, facts: dict) -> asyncio.Task:
    async def run() -> None:
        text = None
        try:
            text = await _complete_with_retry(llm, SYSTEM_PROMPT, context)
        except Exception as primary_exc:
            logger.warning("summary primary model failed: %s", primary_exc)
            if fallback_llm is not None and fallback_llm is not llm:
                try:
                    text = await fallback_llm.complete(SYSTEM_PROMPT, context)
                except Exception:
                    logger.exception("summary generation failed (fallback)")
                    text = None
            else:
                logger.exception("summary generation failed", exc_info=False)
                text = None
        slot.finish(text)
        if text is not None and memory is not None:
            memory.append(week, facts, text)
            memory.save()
            if memory.needs_digest():
                _fold_task = asyncio.create_task(_fold(memory, llm))
                _fold_tasks.add(_fold_task)
                _fold_task.add_done_callback(_fold_tasks.discard)

    return asyncio.create_task(run())


async def _fold(memory: SummaryMemory, llm) -> None:
    """Сворачивает переполнение памяти в дайджест через LLM."""
    try:
        if not memory.needs_digest():
            return
        overflow = memory.overflow()
        if not overflow:
            memory.prune()
            memory.save()
            return
        digest = await llm.complete(DIGEST_PROMPT, memory.render_overflow_text(overflow))
        if digest:
            memory.fold_into_digest(digest)
            memory.save()
    except Exception:
        logger.exception("memory fold failed")


@summary_router.message(SUMMARY_FILTER)
async def handle_summary(
    message: Message, cache, worker, quiz, summary_slot,
    memory: SummaryMemory | None = None,
    today: datetime.date | None = None,
) -> Response:
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
    memory_context = memory.render_memory_block() if memory is not None else ""
    context = summarize_context(
        result.week_schedule,
        result.week_marks,
        result.overdue,
        result.lessons,
        homework,
        target,
        today,
        memory_context=memory_context,
    )
    week = (today - datetime.timedelta(days=today.weekday())).isoformat()
    facts = collect_week_facts(result.week_marks, result.overdue)

    slot = summary_slot
    if slot.has_pending and slot.task is not None and not slot.task.done():
        return Response(text=PREMATURE_SUMMARY_MORE_TEXT)
    if slot.text is not None:
        text = slot.text
        slot.clear()
        return Response(text=text)

    task = _summary_task(
        quiz.summary_llm or quiz.llm, quiz.llm, context, slot, memory, week, facts,
    )
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