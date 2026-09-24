from __future__ import annotations

import asyncio
import logging

from aliceio import F, Router
from aliceio.types import Message, Response

from quiz_library.model import HomeworkEntry

from alice_skill.quiz_state import QuizSlot
from alice_skill.quiz_service import QuizBundle

logger = logging.getLogger(__name__)

quiz_router = Router(name="quiz")

QUIZ_FILTER = F.command.contains("спроси") | F.command.contains("проверь")

DIRECT_TIMEOUT = 3.5

QUIZ_NOT_CONFIGURED_TEXT = "Викторина не настроена. Попроси взрослых включить её."
NO_HOMEWORK_TEXT = "Сегодня по {subject} ничего не задано."
ASK_SUBJECT_TEXT = "По какому предмету спросить?"
NO_PARA_OR_THEME_TEXT = "Не нашла в задании по {subject} ни параграфа, ни темы."
PLATFORM_TEXT = "По {subject} задание на онлайн-платформе {label} — его в учебнике нет."
PREMATURE_QUIZ_TEXT = "Секунду, придумываю вопрос. Скажи «дальше»."
PREMATURE_MORE_TEXT = "Ещё чуть-чуть, придумываю вопрос. Скажи «дальше» ещё раз."
QUIZ_FAIL_TEXT = "Не получилось придумать вопрос. Попробуй ещё раз."


def _quiz_task(service, entry: HomeworkEntry, slot: QuizSlot):
    async def run() -> None:
        try:
            q = await service.question_for(entry)
        except Exception:
            logger.exception("quiz generation failed")
            q = None
        slot.finish(entry.subject, q.text if q else None)

    return asyncio.create_task(run())


def _resolve_subject(command: str, entries: list[HomeworkEntry], names: list[str]) -> str | None:
    # команда «спроси по биологии» — родительный падеж: «биология» напрямую
    # как подстрока не встретится, поэтому сравниваем и по основе без последней буквы
    command_low = command.lower()
    for name in names:
        name_low = name.lower()
        # 1-буквенные названия не проверяем по основе: пустая подстрока "в"
        # есть в любой команде, и предмет совпадёт ложно
        if name_low in command_low or (len(name_low) > 1 and name_low[:-1] in command_low):
            return name
    distinct = {e.subject for e in entries}
    if len(distinct) == 1:
        return distinct.pop()
    return None


def _entry_for(entries: list[HomeworkEntry], subject: str) -> HomeworkEntry | None:
    for e in entries:
        if e.subject.lower() == subject.lower():
            return e
    return None


@quiz_router.message(QUIZ_FILTER)
async def handle_quiz(message: Message, cache, quiz: QuizBundle | None, slot: QuizSlot | None) -> Response:
    if quiz is None or slot is None:
        return Response(text=QUIZ_NOT_CONFIGURED_TEXT)
    service = quiz.service()
    if service is None:
        return Response(text=QUIZ_NOT_CONFIGURED_TEXT)

    result = cache.get()
    entries = list(result.entries) if result is not None else []

    subject = _resolve_subject(message.command, entries, quiz.subject_names)
    if subject is None:
        if not entries:
            return Response(text=NO_HOMEWORK_TEXT.format(subject="этим предметам"))
        return Response(text=ASK_SUBJECT_TEXT)

    entry = _entry_for(entries, subject)
    if entry is None:
        return Response(text=NO_HOMEWORK_TEXT.format(subject=subject.lower()))

    res = service.resolution(entry)
    if res.reason == "platform":
        label = "Сириус" if "сириус" in entry.content.lower() else "платформе"
        return Response(text=PLATFORM_TEXT.format(subject=subject.lower(), label=label))
    if res.reason in ("empty", "none"):
        return Response(text=NO_PARA_OR_THEME_TEXT.format(subject=subject.lower()))
    key = res.choice

    # слот создаётся в create_app, один на процесс (навык однопользовательский):
    # гонки нескольких параллельных сессий намеренно не обрабатываются (спека §2)
    if slot.question is not None and slot.subject is not None and slot.subject.lower() == subject.lower() and slot.paragraph == key:
        text = slot.question
        slot.clear()
        return Response(text=text)

    if (
        slot.task is not None
        and not slot.task.done()
        and slot.subject is not None
        and slot.subject.lower() == subject.lower()
        and slot.paragraph == key
    ):
        return Response(text=PREMATURE_QUIZ_TEXT)

    task = _quiz_task(service, entry, slot)
    slot.set_pending(subject=subject, paragraph=key, task=task)

    done, _ = await asyncio.wait({task}, timeout=DIRECT_TIMEOUT)
    if task in done:
        if slot.question is not None:
            text = slot.question
            slot.clear()
            return Response(text=text)
        slot.clear()
        return Response(text=QUIZ_FAIL_TEXT)
    return Response(text=PREMATURE_QUIZ_TEXT)