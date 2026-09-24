import asyncio
from unittest.mock import MagicMock

import pytest

from alice_skill.cache import HomeworkCache
from alice_skill.handlers.quiz import (
    ASK_SUBJECT_TEXT,
    NO_HOMEWORK_TEXT,
    NO_PARAGRAPH_TEXT,
    PREMATURE_QUIZ_TEXT,
    QUIZ_FAIL_TEXT,
    QUIZ_NOT_CONFIGURED_TEXT,
    handle_quiz,
)
from alice_skill.quiz_state import QuizSlot
from quiz_library.model import HomeworkEntry, Question


def _entry(content="параграф 6", subject="География"):
    return HomeworkEntry(subject=subject, content=content)


def _cache(*entries):
    cache = HomeworkCache()
    if entries:
        cache.set(MagicMock(status="ok", entries=list(entries)))
    return cache


class _FakeService:
    def __init__(self, question_for=None, patterns=("параграф", "§")):
        self._impl = question_for or self._async_none
        self._calls = 0
        self.patterns = patterns

    async def _async_none(self, entry):
        return None

    async def question_for(self, entry):
        self._calls += 1
        return await self._impl(entry)

    def patterns_for(self, subject):
        return list(self.patterns)


def _bundle(service):
    b = MagicMock()
    b.service.return_value = service
    type(b).subject_names = property(lambda self: ["География", "Биология"])
    return b


@pytest.mark.asyncio
async def test_not_configured_when_quiz_missing():
    cache = _cache(_entry())
    slot = QuizSlot()
    resp = await handle_quiz(
        MagicMock(command="спроси по географии"), cache=cache, quiz=None, slot=slot,
    )
    assert resp.text == QUIZ_NOT_CONFIGURED_TEXT


@pytest.mark.asyncio
async def test_not_configured_when_subjects_missing():
    b = MagicMock()
    b.service.return_value = None
    cache = _cache(_entry())
    resp = await handle_quiz(
        MagicMock(command="спроси по географии"), cache=cache, quiz=b, slot=QuizSlot(),
    )
    assert resp.text == QUIZ_NOT_CONFIGURED_TEXT


@pytest.mark.asyncio
async def test_no_entries():
    cache = _cache()
    b = _bundle(_FakeService())
    resp = await handle_quiz(
        MagicMock(command="спроси по географии"), cache=cache, quiz=b, slot=QuizSlot(),
    )
    assert "ничего не задано" in resp.text.lower()


@pytest.mark.asyncio
async def test_no_entry_for_subject():
    cache = _cache(_entry(subject="Биология"))
    b = _bundle(_FakeService())
    resp = await handle_quiz(
        MagicMock(command="спроси по географии"), cache=cache, quiz=b, slot=QuizSlot(),
    )
    # предмет найден по основе, но записи по нему нет
    assert "ничего не задано" in resp.text.lower()
    assert "география" in resp.text.lower()


@pytest.mark.asyncio
async def test_case_insensitive_subject():
    cache = _cache(_entry())
    b = _bundle(_FakeService())
    resp = await handle_quiz(
        MagicMock(command="спроси по ГЕОГРАФИИ"), cache=cache, quiz=b, slot=QuizSlot(),
    )
    # предмет найден; вопрос не задан (fake возвращает None)
    assert resp.text == QUIZ_FAIL_TEXT


@pytest.mark.asyncio
async def test_no_paragraph():
    cache = _cache(_entry(content="прочитать", subject="География"))
    b = _bundle(_FakeService())
    resp = await handle_quiz(
        MagicMock(command="спроси по географии"), cache=cache, quiz=b, slot=QuizSlot(),
    )
    assert "параграф" in resp.text


@pytest.mark.asyncio
async def test_ask_subject_when_many():
    cache = _cache(_entry(subject="География"), _entry(subject="Биология"))
    b = _bundle(_FakeService())
    resp = await handle_quiz(
        MagicMock(command="спроси"), cache=cache, quiz=b, slot=QuizSlot(),
    )
    assert resp.text == ASK_SUBJECT_TEXT


@pytest.mark.asyncio
async def test_immediate_answer():
    async def give(entry):
        return Question(subject="География", paragraph=6, paragraph_title="Газовая",
                        pages=(22, 25), text="Какой вопрос?")

    cache = _cache(_entry())
    b = _bundle(_FakeService(question_for=give))
    slot = QuizSlot()
    resp = await handle_quiz(
        MagicMock(command="спроси по географии"), cache=cache, quiz=b, slot=slot,
    )
    assert resp.text == "Какой вопрос?"
    assert slot.has_pending is False


@pytest.mark.asyncio
async def test_slow_answer_promises_question(monkeypatch):
    monkeypatch.setattr("alice_skill.handlers.quiz.DIRECT_TIMEOUT", 0.1)
    release = asyncio.Event()

    async def slow(entry):
        await release.wait()
        return Question(subject="География", paragraph=6, paragraph_title="Газовая",
                        pages=(22, 25), text="Готовый вопрос.")

    cache = _cache(_entry())
    b = _bundle(_FakeService(question_for=slow))
    slot = QuizSlot()
    resp = await handle_quiz(
        MagicMock(command="спроси по географии"), cache=cache, quiz=b, slot=slot,
    )
    assert resp.text == PREMATURE_QUIZ_TEXT
    assert slot.task is not None
    assert slot.subject == "География"
    release.set()
    await slot.task  # эстафетный сигнал уже отдан; дожидаемся фоновой генерации
    assert slot.question == "Готовый вопрос."


@pytest.mark.asyncio
async def test_repeat_trigger_does_not_spawn_second_call(monkeypatch):
    monkeypatch.setattr("alice_skill.handlers.quiz.DIRECT_TIMEOUT", 0.1)
    release = asyncio.Event()

    async def slow(entry):
        await release.wait()
        return Question(subject="География", paragraph=6, paragraph_title="Газовая",
                        pages=(22, 25), text="Готовый вопрос.")

    cache = _cache(_entry())
    b = _bundle(_FakeService(question_for=slow))
    slot = QuizSlot()
    first = await handle_quiz(
        MagicMock(command="спроси по географии"), cache=cache, quiz=b, slot=slot,
    )
    assert first.text == PREMATURE_QUIZ_TEXT
    second = await handle_quiz(
        MagicMock(command="спроси по географии"), cache=cache, quiz=b, slot=slot,
    )
    assert second.text == PREMATURE_QUIZ_TEXT
    assert b.service.return_value._calls == 1  # single-flight: второй вызов не порождён
    release.set()
    await slot.task
    assert slot.question == "Готовый вопрос."


@pytest.mark.asyncio
async def test_ready_question_served_from_slot(monkeypatch):
    monkeypatch.setattr("alice_skill.handlers.quiz.DIRECT_TIMEOUT", 0.1)
    release = asyncio.Event()

    async def slow(entry):
        await release.wait()
        return Question(subject="География", paragraph=6, paragraph_title="Газовая",
                        pages=(22, 25), text="Готовый вопрос.")

    cache = _cache(_entry())
    b = _bundle(_FakeService(question_for=slow))
    slot = QuizSlot()
    await handle_quiz(MagicMock(command="спроси по географии"), cache=cache, quiz=b, slot=slot)
    release.set()
    await slot.task
    resp = await handle_quiz(
        MagicMock(command="спроси по географии"), cache=cache, quiz=b, slot=slot,
    )
    assert resp.text == "Готовый вопрос."
    assert slot.has_pending is False


@pytest.mark.asyncio
async def test_ready_question_not_served_for_other_paragraph():
    cache = _cache(_entry(content="параграф 7", subject="География"))
    async def give(entry):
        return Question(subject="География", paragraph=7, paragraph_title="Другая",
                        pages=(1, 3), text="Вопрос про параграф 7.")

    b = _bundle(_FakeService(question_for=give))
    slot = QuizSlot()
    slot.subject = "География"
    slot.question = "Старый вопрос про параграф 6."
    slot.paragraph = 6
    resp = await handle_quiz(
        MagicMock(command="спроси по географии"), cache=cache, quiz=b, slot=slot,
    )
    assert resp.text == "Вопрос про параграф 7."
    assert slot.has_pending is False


def test_resolve_subject_ignores_one_char_names():
    from alice_skill.handlers.quiz import _resolve_subject

    names = ["Щ", "География", "Биология"]
    entries = [
        HomeworkEntry(subject="География", content="параграф 4"),
        HomeworkEntry(subject="Биология", content="параграф 4"),
    ]
    # пустая основа «Щ»[:-1] = "" не должна ловить любую команду;
    # два предмета, чтобы fallback (единственный отличный предмет) не сработал
    assert _resolve_subject("спроси по биологии", entries, names) == "Биология"


@pytest.mark.asyncio
async def test_genitive_subject_matches_command(monkeypatch):
    # «по биологии» (родительный падеж) находит предмет «Биология»
    monkeypatch.setattr("alice_skill.handlers.quiz.DIRECT_TIMEOUT", 0.1)
    cache = _cache(_entry(subject="География"), _entry(subject="Биология"))
    b = _bundle(_FakeService())
    resp = await handle_quiz(
        MagicMock(command="спроси по биологии"), cache=cache, quiz=b, slot=QuizSlot(),
    )
    assert resp.text == QUIZ_FAIL_TEXT  # предмет найден, fake-вопрос не генерируется