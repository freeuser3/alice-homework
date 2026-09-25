import asyncio
import datetime
from unittest.mock import MagicMock

import pytest

from alice_skill.cache import HomeworkCache
from alice_skill.handlers.summary import (
    DIRECT_TIMEOUT,
    DIGEST_PROMPT,
    PREMATURE_SUMMARY_MORE_TEXT,
    PREMATURE_SUMMARY_TEXT,
    SUMMARY_FAIL_TEXT,
    SUMMARY_NOT_CONFIGURED_TEXT,
    SYSTEM_PROMPT,
    handle_summary,
)
from alice_skill.memory_store import SummaryMemory
from alice_skill.quiz_state import SummarySlot
from quiz_library.model import HomeworkEntry

TODAY = datetime.date(2026, 9, 21)      # Monday
TOMORROW = datetime.date(2026, 9, 22)   # Tuesday


def _result(**overrides):
    base = {
        "status": "ok",
        "target_date": TOMORROW,
        "text": "домашка",
        "lessons": ["Физика"],
        "lessons_text": "уроки",
        "entries": [HomeworkEntry(subject="Алгебра", content="Упр. 5")],
        "marks": {},
        "week_schedule": {"2026-09-21": ["Алгебра"]},
        "week_marks": [{"day": "2026-09-21", "subject": "Алгебра", "mark": 5, "comment": ""}],
        "overdue": [],
    }
    base.update(overrides)
    return MagicMock(**base)


def _cache(result):
    cache = HomeworkCache()
    cache.set(result)
    return cache


def _bundle(llm):
    b = MagicMock()
    b.llm = llm
    return b


class _FakeLlm:
    def __init__(self, result):
        self._result = result
        self.calls = []

    async def complete(self, system, user):
        self.calls.append((system, user))
        if callable(self._result):
            return await self._result()
        return self._result


@pytest.mark.asyncio
async def test_not_configured_when_quiz_missing():
    cache = _cache(_result())
    resp = await handle_summary(
        MagicMock(command="итоги за неделю"), cache=cache, worker=MagicMock(),
        quiz=None, summary_slot=SummarySlot(),
    )
    assert resp.text == SUMMARY_NOT_CONFIGURED_TEXT


@pytest.mark.asyncio
async def test_not_configured_when_llm_missing():
    cache = _cache(_result())
    resp = await handle_summary(
        MagicMock(command="итоги за неделю"), cache=cache, worker=MagicMock(),
        quiz=MagicMock(llm=None), summary_slot=SummarySlot(),
    )
    assert resp.text == SUMMARY_NOT_CONFIGURED_TEXT


@pytest.mark.asyncio
async def test_empty_cache_promises_premature():
    llm = _FakeLlm("Итог недели.")
    cache = HomeworkCache()
    worker = MagicMock()
    resp = await handle_summary(
        MagicMock(command="итоги за неделю"), cache=cache, worker=worker,
        quiz=_bundle(llm), summary_slot=SummarySlot(),
    )
    assert resp.text == "Секунду, заглядываю в дневник. Скажи «дальше»."
    worker.refresh_now.assert_called_once()


@pytest.mark.asyncio
async def test_error_cache_promises_premature():
    llm = _FakeLlm("Итог недели.")
    cache = _cache(_result(status="error"))
    worker = MagicMock()
    resp = await handle_summary(
        MagicMock(command="итоги за неделю"), cache=cache, worker=worker,
        quiz=_bundle(llm), summary_slot=SummarySlot(),
    )
    assert resp.text == "Секунду, заглядываю в дневник. Скажи «дальше»."
    worker.refresh_now.assert_called_once()


@pytest.mark.asyncio
async def test_immediate_answer():
    llm = _FakeLlm("Молодец, в неделе был один спокойный предмет.")
    slot = SummarySlot()
    resp = await handle_summary(
        MagicMock(command="итоги за неделю"), cache=_cache(_result()),
        worker=MagicMock(), quiz=_bundle(llm), summary_slot=slot,
    )
    assert resp.text == "Молодец, в неделе был один спокойный предмет."
    assert slot.has_pending is False


@pytest.mark.asyncio
async def test_context_contains_schedule_and_marks():
    llm = _FakeLlm("Итог.")
    await handle_summary(
        MagicMock(command="итоги за неделю"), cache=_cache(_result()),
        worker=MagicMock(), quiz=_bundle(llm), summary_slot=SummarySlot(),
    )
    system, user = llm.calls[0]
    assert system == SYSTEM_PROMPT
    assert "2026-09-21" in user
    assert "Алгебра" in user
    assert "Уроки на завтра" in user
    assert "Домашнее задание на завтра" in user


@pytest.mark.asyncio
async def test_slow_answer_promises_more(monkeypatch):
    monkeypatch.setattr("alice_skill.handlers.summary.DIRECT_TIMEOUT", 0.1)
    release = asyncio.Event()

    async def slow():
        await release.wait()
        return "Готовый итог."

    llm = _FakeLlm(slow)
    slot = SummarySlot()
    resp = await handle_summary(
        MagicMock(command="итоги за неделю"), cache=_cache(_result()),
        worker=MagicMock(), quiz=_bundle(llm), summary_slot=slot,
    )
    assert resp.text == PREMATURE_SUMMARY_TEXT
    assert slot.task is not None
    release.set()
    await slot.task
    assert slot.text == "Готовый итог."


@pytest.mark.asyncio
async def test_ready_text_served_from_slot(monkeypatch):
    monkeypatch.setattr("alice_skill.handlers.summary.DIRECT_TIMEOUT", 0.1)
    release = asyncio.Event()

    async def slow():
        await release.wait()
        return "Готовый итог."

    slot = SummarySlot()
    await handle_summary(
        MagicMock(command="итоги за неделю"), cache=_cache(_result()),
        worker=MagicMock(), quiz=_bundle(_FakeLlm(slow)), summary_slot=slot,
    )
    release.set()
    await slot.task
    resp = await handle_summary(
        MagicMock(command="итоги за неделю"), cache=_cache(_result()),
        worker=MagicMock(), quiz=_bundle(_FakeLlm(slow)), summary_slot=slot,
    )
    assert resp.text == "Готовый итог."
    assert slot.has_pending is False


@pytest.mark.asyncio
async def test_repeat_trigger_does_not_spawn_second_call(monkeypatch):
    monkeypatch.setattr("alice_skill.handlers.summary.DIRECT_TIMEOUT", 0.1)
    release = asyncio.Event()

    async def slow():
        await release.wait()
        return "Готовый итог."

    llm = _FakeLlm(slow)
    slot = SummarySlot()
    first = await handle_summary(
        MagicMock(command="итоги за неделю"), cache=_cache(_result()),
        worker=MagicMock(), quiz=_bundle(llm), summary_slot=slot,
    )
    assert first.text == PREMATURE_SUMMARY_TEXT
    second = await handle_summary(
        MagicMock(command="итоги за неделю"), cache=_cache(_result()),
        worker=MagicMock(), quiz=_bundle(llm), summary_slot=slot,
    )
    assert second.text == PREMATURE_SUMMARY_MORE_TEXT
    assert len(llm.calls) == 1
    release.set()
    await slot.task
    assert slot.text == "Готовый итог."


@pytest.mark.asyncio
async def test_failed_generation_returns_fail_text(monkeypatch):
    monkeypatch.setattr("alice_skill.handlers.summary.DIRECT_TIMEOUT", 0.1)

    async def boom():
        raise RuntimeError("llm down")

    llm = _FakeLlm(boom)
    slot = SummarySlot()
    resp = await handle_summary(
        MagicMock(command="итоги за неделю"), cache=_cache(_result()),
        worker=MagicMock(), quiz=_bundle(llm), summary_slot=slot,
    )
    assert resp.text == SUMMARY_FAIL_TEXT
    assert slot.has_pending is False


@pytest.mark.asyncio
async def test_no_target_date_uses_tomorrow():
    llm = _FakeLlm("Итог.")
    result = _result(status="empty", target_date=None, entries=[], lessons=[])
    await handle_summary(
        MagicMock(command="итоги за неделю"), cache=_cache(result),
        worker=MagicMock(), quiz=_bundle(llm), summary_slot=SummarySlot(),
        today=TODAY,
    )
    _, user = llm.calls[0]
    assert "Уроки на завтра" in user
    assert "вторник 22.09" in user


def test_summary_slot_isolation():
    # summary_slot и quiz slot не должны конфликтовать (отдельные объекты)
    s = SummarySlot()
    assert s.text is None
    assert s.task is None
    assert s.has_pending is False


# --- память наставника ---

def _memory(tmp_path, max_weeks=8):
    m = SummaryMemory(tmp_path / "memory.json", max_weeks=max_weeks)
    m.load()
    return m


@pytest.mark.asyncio
async def test_memory_saved_after_immediate_answer(tmp_path):
    llm = _FakeLlm("Итог: три пятёрки.")
    memory = _memory(tmp_path, max_weeks=8)
    resp = await handle_summary(
        MagicMock(command="итоги за неделю"), cache=_cache(_result()),
        worker=MagicMock(), quiz=_bundle(llm), summary_slot=SummarySlot(),
        today=TODAY, memory=memory,
    )
    assert resp.text == "Итог: три пятёрки."
    assert len(memory.weeks) == 1
    entry = memory.weeks[0]
    assert entry["week"] == "2026-09-21"
    assert entry["facts"]["marks_count"] == 1
    assert entry["facts"]["avg"] == 5.0
    assert entry["summary"] == "Итог: три пятёрки."
    assert (tmp_path / "memory.json").exists()


@pytest.mark.asyncio
async def test_memory_context_feeds_llm(tmp_path):
    llm = _FakeLlm("Итог.")
    memory = _memory(tmp_path, max_weeks=8)
    memory.append("2026-09-14", {"marks_count": 2, "avg": 4.0}, "прошлый итог")
    memory.digest = "алгебра растёт"
    await handle_summary(
        MagicMock(command="итоги за неделю"), cache=_cache(_result()),
        worker=MagicMock(), quiz=_bundle(llm), summary_slot=SummarySlot(),
        today=TODAY, memory=memory,
    )
    _, user = llm.calls[0]
    assert "Память о прошлых неделях" in user
    assert "алгебра растёт" in user
    assert "2026-09-14" in user


@pytest.mark.asyncio
async def test_no_memory_block_when_memory_missing():
    llm = _FakeLlm("Итог.")
    await handle_summary(
        MagicMock(command="итоги за неделю"), cache=_cache(_result()),
        worker=MagicMock(), quiz=_bundle(llm), summary_slot=SummarySlot(),
        today=TODAY,
    )
    _, user = llm.calls[0]
    assert "Память о прошлых неделях" not in user


@pytest.mark.asyncio
async def test_digest_generated_on_threshold(tmp_path):
    llm = _FakeLlm("Итог недели.")
    memory = _memory(tmp_path, max_weeks=3)
    for i in range(2):
        memory.append(f"2026-09-{7 + i}", {"marks_count": 1, "avg": 4.0}, f"старый {i}")
    await handle_summary(
        MagicMock(command="итоги за неделю"), cache=_cache(_result()),
        worker=MagicMock(), quiz=_bundle(llm), summary_slot=SummarySlot(),
        today=TODAY, memory=memory,
    )
    # после добавления третьей недели должен запуститься фоновый дайджест
    await asyncio.sleep(0)
    assert memory.digest == "Итог недели."
    assert len(memory.weeks) == 2
    assert len(llm.calls) == 2
    system, _ = llm.calls[1]
    assert system == DIGEST_PROMPT


@pytest.mark.asyncio
async def test_no_digest_below_threshold(tmp_path):
    llm = _FakeLlm("Итог недели.")
    memory = _memory(tmp_path, max_weeks=10)
    await handle_summary(
        MagicMock(command="итоги за неделю"), cache=_cache(_result()),
        worker=MagicMock(), quiz=_bundle(llm), summary_slot=SummarySlot(),
        today=TODAY, memory=memory,
    )
    await asyncio.sleep(0)
    assert memory.digest == ""
    assert len(memory.weeks) == 1
    assert len(llm.calls) == 1