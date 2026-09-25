import json

from alice_skill.memory_store import (
    SummaryMemory,
    render_facts_line,
)


def _memory(path, max_weeks=8):
    m = SummaryMemory(path, max_weeks=max_weeks)
    m.load()
    return m


def _entry(week, summary="итог", marks_count=1, avg=4.0):
    return {
        "week": week,
        "facts": {"marks_count": marks_count, "avg": avg, "strong": [], "weak": [], "overdue": 0},
        "summary": summary,
    }


def test_append_and_save_load_roundtrip(tmp_path):
    path = tmp_path / "memory.json"
    m = _memory(path)
    m.append("2026-09-21", _entry("2026-09-21")["facts"], "хорошая неделя")
    m.digest = "общий итог"
    m.save()

    loaded = _memory(path)
    assert len(loaded.weeks) == 1
    assert loaded.weeks[0]["week"] == "2026-09-21"
    assert loaded.weeks[0]["summary"] == "хорошая неделя"
    assert loaded.digest == "общий итог"


def test_load_missing_file_gives_empty_state(tmp_path):
    m = _memory(tmp_path / "nope.json")
    assert m.weeks == []
    assert m.digest == ""


def test_load_corrupt_file_gives_empty_state(tmp_path):
    path = tmp_path / "memory.json"
    path.write_text("{not json", encoding="utf-8")
    m = _memory(path)
    assert m.weeks == []
    assert m.digest == ""


def test_prune_limits_weeks(tmp_path):
    m = _memory(tmp_path / "memory.json", max_weeks=3)
    for i in range(5):
        m.append(f"2026-09-{i + 1:02d}", {}, f"{i}")
    m.prune()
    assert [w["week"] for w in m.weeks] == ["2026-09-03", "2026-09-04", "2026-09-05"]


def test_needs_digest_at_threshold(tmp_path):
    m = _memory(tmp_path / "memory.json", max_weeks=4)
    assert m.needs_digest() is False
    for i in range(4):
        m.append(f"2026-09-{i + 1:02d}", {}, str(i))
    assert m.needs_digest() is True


def test_overflow_returns_all_but_last_two(tmp_path):
    m = _memory(tmp_path / "memory.json")
    for i in range(5):
        m.append(f"2026-09-{i + 1:02d}", {}, str(i))
    overflow = m.overflow()
    assert [w["week"] for w in overflow] == ["2026-09-01", "2026-09-02", "2026-09-03"]
    assert len(m.weeks) == 5


def test_overflow_empty_for_two_or_less(tmp_path):
    m = _memory(tmp_path / "memory.json")
    m.append("2026-09-01", {}, "a")
    m.append("2026-09-02", {}, "b")
    assert m.overflow() == []


def test_fold_into_digest_keeps_last_two(tmp_path):
    m = _memory(tmp_path / "memory.json")
    for i in range(5):
        m.append(f"2026-09-{i + 1:02d}", {}, str(i))
    m.fold_into_digest("сжато")
    assert m.digest == "сжато"
    assert [w["week"] for w in m.weeks] == ["2026-09-04", "2026-09-05"]


def test_render_memory_block_combines_digest_and_recent(tmp_path):
    m = _memory(tmp_path / "memory.json")
    m.digest = "алгебра растёт"
    m.append("2026-09-14", {}, "первый")
    m.append("2026-09-07", {}, "второй")
    block = m.render_memory_block()
    assert "Дайджест прошлых недель: алгебра растёт" in block
    assert "Прошлая неделя 2026-09-14" in block
    assert "Прошлая неделя 2026-09-07" in block
    assert "2026-09-01" not in block


def test_render_memory_block_empty():
    m = SummaryMemory("unused.json")
    assert m.render_memory_block() == ""


def test_render_overflow_text_includes_digest_and_facts(tmp_path):
    m = _memory(tmp_path / "memory.json")
    m.digest = "старый дайджест"
    facts = {"marks_count": 5, "avg": 4.2, "strong": ["алгебра"], "weak": [], "overdue": 1}
    m.append("2026-09-05", {}, "самая старая")
    m.append("2026-09-07", facts, "было нормально")
    m.append("2026-09-14", {}, "недавняя")
    m.append("2026-09-15", {}, "последняя")
    text = m.render_overflow_text(m.overflow())
    assert "Прежний дайджест: старый дайджест" in text
    assert "Неделя 2026-09-05" in text
    assert "Неделя 2026-09-07" in text
    assert "средний балл 4.2" in text
    assert "сильные: алгебра" in text
    assert "долгов: 1" in text
    assert "было нормально" in text
    assert "2026-09-14" not in text
    assert "2026-09-15" not in text


def test_facts_rendering():
    assert render_facts_line(
        {"marks_count": 3, "avg": 4.7, "strong": ["физика"], "weak": ["химия"], "overdue": 2}
    ) == "средний балл 4.7; оценок: 3; сильные: физика; слабые: химия; долгов: 2"


def test_facts_rendering_minimal():
    assert render_facts_line({"marks_count": 0, "avg": None, "strong": [], "weak": [], "overdue": 0}) == ""