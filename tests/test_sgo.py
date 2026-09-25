import datetime
from datetime import time
from unittest.mock import AsyncMock, patch

import pytest

from alice_skill.sgo import ERROR_TEXT, HomeworkResult, fetch_homework
from netschoolapi_plus.schemas import Assignment, Day, Diary, Lesson


def _make_diary_for(target: datetime.date, lessons: list[Lesson]) -> Diary:
    return Diary(
        start=target,
        end=target + datetime.timedelta(days=7),
        schedule=[Day(lessons=lessons, day=target)],
    )


def _make_lesson(number: int, subject: str, assignments: list[Assignment]) -> Lesson:
    return Lesson(
        day=datetime.date(2026, 9, 21),
        start=time(9, 0),
        end=time(9, 45),
        room="101",
        number=number,
        subject=subject,
        assignments=assignments,
    )


def _make_assignment(aid: int, type_: str, content: str) -> Assignment:
    return Assignment(
        id=aid, comment="", type=type_, content=content,
        mark=None, is_duty=False, deadline=time(23, 59),
    )


@pytest.mark.asyncio
async def test_fetch_homework_ok():
    target = datetime.date(2026, 9, 21)
    lesson = _make_lesson(1, "Алгебра", [_make_assignment(1, "Домашнее задание", "Упр. 5")])
    fake_diary = _make_diary_for(target, [lesson])

    mock_ns = AsyncMock()
    mock_ns.diary = AsyncMock(return_value=fake_diary)
    mock_ns.attachments = AsyncMock(return_value=[])
    mock_ns.logout = AsyncMock()

    with patch("alice_skill.sgo.NetSchoolAPI", return_value=mock_ns):
        result = await fetch_homework("u", "p", "s", now=datetime.date(2026, 9, 20))

    assert result.status == "ok"
    assert result.target_date == target
    assert "алгебра" in result.text
    assert "Упражнение 5" in result.text
    mock_ns.login.assert_awaited_once_with("u", "p", "s")
    mock_ns.logout.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_homework_empty():
    target = datetime.date(2026, 9, 21)
    lesson = _make_lesson(
        1, "Алгебра",
        [_make_assignment(1, "Ответ на уроке", "---")],
    )
    fake_diary = _make_diary_for(target, [lesson])

    mock_ns = AsyncMock()
    mock_ns.diary = AsyncMock(return_value=fake_diary)
    mock_ns.logout = AsyncMock()

    with patch("alice_skill.sgo.NetSchoolAPI", return_value=mock_ns):
        result = await fetch_homework("u", "p", "s", now=datetime.date(2026, 9, 20))

    assert result.status == "empty"
    assert "отдыхать" in result.text


@pytest.mark.asyncio
async def test_fetch_homework_error_returns_error_text():
    mock_ns = AsyncMock()
    mock_ns.login = AsyncMock(side_effect=RuntimeError("network down"))
    mock_ns.logout = AsyncMock()

    with patch("alice_skill.sgo.NetSchoolAPI", return_value=mock_ns):
        result = await fetch_homework("u", "p", "s")

    assert result.status == "error"
    assert result.text == ERROR_TEXT
    assert "network down" in result.error


@pytest.mark.asyncio
async def test_fetch_homework_attaches_attachment_names():
    from netschoolapi_plus.schemas import Attachment

    target = datetime.date(2026, 9, 21)
    lesson = _make_lesson(1, "Литература", [_make_assignment(10, "Домашнее задание", "Прочитать")])
    fake_diary = _make_diary_for(target, [lesson])

    mock_ns = AsyncMock()
    mock_ns.diary = AsyncMock(return_value=fake_diary)
    mock_ns.attachments = AsyncMock(
        return_value=[Attachment(id=10, name="задание.docx", description="")]
    )
    mock_ns.logout = AsyncMock()

    with patch("alice_skill.sgo.NetSchoolAPI", return_value=mock_ns):
        result = await fetch_homework("u", "p", "s", now=datetime.date(2026, 9, 20))

    assert result.status == "ok"
    mock_ns.attachments.assert_awaited_once_with(10)


@pytest.mark.asyncio
async def test_fetch_homework_logout_called_on_error():
    mock_ns = AsyncMock()
    mock_ns.login = AsyncMock(return_value=None)
    mock_ns.diary = AsyncMock(side_effect=RuntimeError("boom"))
    mock_ns.logout = AsyncMock()

    with patch("alice_skill.sgo.NetSchoolAPI", return_value=mock_ns):
        result = await fetch_homework("u", "p", "s")

    assert result.status == "error"
    mock_ns.logout.assert_awaited_once()


def test_fetch_homework_result_entries_exists():
    result = HomeworkResult(status="empty", target_date=None, text="")
    assert result.entries == []


@pytest.mark.asyncio
async def test_fetch_homework_ok_fills_entries():
    target = datetime.date(2026, 9, 21)
    lesson = _make_lesson(
        1, "География",
        [_make_assignment(1, "Домашнее задание", "<p>параграф 6</p>")],
    )
    fake_diary = _make_diary_for(target, [lesson])

    mock_ns = AsyncMock()
    mock_ns.diary = AsyncMock(return_value=fake_diary)
    mock_ns.attachments = AsyncMock(return_value=[])
    mock_ns.logout = AsyncMock()

    with patch("alice_skill.sgo.NetSchoolAPI", return_value=mock_ns):
        result = await fetch_homework("u", "p", "s", now=datetime.date(2026, 9, 20))

    assert result.status == "ok"
    assert len(result.entries) == 1
    entry = result.entries[0]
    assert entry.subject == "География"
    assert entry.content == "параграф 6"


@pytest.mark.asyncio
async def test_fetch_homework_fills_lessons():
    target = datetime.date(2026, 9, 21)
    l0 = _make_lesson(0, "Классный час", [])
    l1 = _make_lesson(1, "География", [_make_assignment(1, "Домашнее задание", "параграф 6")])
    fake_diary = _make_diary_for(target, [l1, l0])

    mock_ns = AsyncMock()
    mock_ns.diary = AsyncMock(return_value=fake_diary)
    mock_ns.attachments = AsyncMock(return_value=[])
    mock_ns.logout = AsyncMock()

    with patch("alice_skill.sgo.NetSchoolAPI", return_value=mock_ns):
        result = await fetch_homework("u", "p", "s", now=datetime.date(2026, 9, 20))

    assert result.lessons == ["Классный час", "География"]
    assert "уроки с нулевого" in result.lessons_text
    assert "классный час" in result.lessons_text
    assert "география" in result.lessons_text


@pytest.mark.asyncio
async def test_fetch_homework_fills_marks():
    monday = datetime.date(2026, 9, 21)   # оценка в текущую неделю
    thursday = datetime.date(2026, 9, 24)  # домашнее задание в будущий день
    mon_lesson = _make_lesson(
        1, "Алгебра",
        [
            Assignment(
                id=3, comment="", type="Ответ на уроке", content="",
                mark=2, is_duty=False, deadline=datetime.time(23, 59),
            ),
        ],
    )
    thu_lesson = _make_lesson(
        1, "География",
        [_make_assignment(4, "Домашнее задание", "параграф 6")],
    )
    diary = Diary(
        start=monday,
        end=datetime.date(2026, 9, 27),
        schedule=[
            Day(lessons=[mon_lesson], day=monday),
            Day(lessons=[thu_lesson], day=thursday),
        ],
    )

    mock_ns = AsyncMock()
    mock_ns.diary = AsyncMock(return_value=diary)
    mock_ns.attachments = AsyncMock(return_value=[])
    mock_ns.overdue = AsyncMock(return_value=[])
    mock_ns.logout = AsyncMock()

    with patch("alice_skill.sgo.NetSchoolAPI", return_value=mock_ns):
        result = await fetch_homework(
            "u", "p", "s",
            now=datetime.date(2026, 9, 21),
        )

    assert result.status == "ok"
    assert result.target_date == thursday
    assert result.marks == {2: {"Алгебра": 1}}
    assert result.week_schedule == {
        "2026-09-21": ["Алгебра"],
        "2026-09-24": ["География"],
    }
    assert result.week_marks == [
        {"day": "2026-09-21", "subject": "Алгебра", "mark": 2, "comment": ""},
    ]
    assert result.overdue == []


@pytest.mark.asyncio
async def test_fetch_homework_fills_overdue():
    target = datetime.date(2026, 9, 21)
    lesson = _make_lesson(1, "Алгебра", [_make_assignment(1, "Домашнее задание", "Упр. 5")])
    fake_diary = _make_diary_for(target, [lesson])

    overdue_assign = Assignment(
        id=7, comment="", type="Домашнее задание", content="Параграф 3",
        mark=None, is_duty=False, deadline=datetime.date(2026, 9, 18),
    )

    mock_ns = AsyncMock()
    mock_ns.diary = AsyncMock(return_value=fake_diary)
    mock_ns.attachments = AsyncMock(return_value=[])
    mock_ns.overdue = AsyncMock(return_value=[overdue_assign])
    mock_ns.logout = AsyncMock()

    with patch("alice_skill.sgo.NetSchoolAPI", return_value=mock_ns):
        result = await fetch_homework("u", "p", "s", now=datetime.date(2026, 9, 20))

    assert result.status == "ok"
    assert result.overdue == [{"content": "Параграф 3", "deadline": "2026-09-18"}]
    mock_ns.overdue.assert_awaited()


@pytest.mark.asyncio
async def test_fetch_homework_overdue_errors_do_not_break_result():
    target = datetime.date(2026, 9, 21)
    lesson = _make_lesson(1, "Алгебра", [_make_assignment(1, "Домашнее задание", "Упр. 5")])
    fake_diary = _make_diary_for(target, [lesson])

    mock_ns = AsyncMock()
    mock_ns.diary = AsyncMock(return_value=fake_diary)
    mock_ns.attachments = AsyncMock(return_value=[])
    mock_ns.overdue = AsyncMock(side_effect=RuntimeError("no overdue endpoint"))
    mock_ns.logout = AsyncMock()

    with patch("alice_skill.sgo.NetSchoolAPI", return_value=mock_ns):
        result = await fetch_homework("u", "p", "s", now=datetime.date(2026, 9, 20))

    assert result.status == "ok"
    assert result.overdue == []