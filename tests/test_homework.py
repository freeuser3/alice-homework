import datetime
import random

from alice_skill.homework import (
    EMPTY_TEXT,
    attachments_phrase,
    collect_homework,
    format_for_voice,
    next_school_day,
    number_to_words,
    number_to_words_instrumental,
    plural_count,
)
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
        start=datetime.time(9, 0),
        end=datetime.time(9, 45),
        room="101",
        number=number,
        subject=subject,
        assignments=assignments,
    )


def _make_assignment(aid: int, type_: str, content: str) -> Assignment:
    return Assignment(
        id=aid, comment="", type=type_, content=content,
        mark=None, is_duty=False, deadline=datetime.time(23, 59),
    )


# --- number words ---

def test_number_to_words():
    assert number_to_words(0) == "ноль"
    assert number_to_words(1) == "одно"
    assert number_to_words(2) == "два"
    assert number_to_words(5) == "пять"
    assert number_to_words(11) == "одиннадцать"
    assert number_to_words(20) == "двадцать"
    assert number_to_words(21) == "двадцать одно"
    assert number_to_words(42) == "сорок два"
    assert number_to_words(99) == "девяносто девять"


def test_number_to_words_instrumental():
    assert number_to_words_instrumental(3) == "тремя"
    assert number_to_words_instrumental(4) == "четырьмя"
    assert number_to_words_instrumental(5) == "пятью"
    assert number_to_words_instrumental(6) == "шестью"
    assert number_to_words_instrumental(15) == "пятнадцатью"
    assert number_to_words_instrumental(25) == "двадцатью пятью"


def test_plural_count():
    assert plural_count(1) == "задание"
    assert plural_count(2) == "задания"
    assert plural_count(5) == "заданий"
    assert plural_count(11) == "заданий"
    assert plural_count(21) == "задание"
    assert plural_count(25) == "заданий"
    assert plural_count(32) == "задания"


def test_attachments_phrase():
    assert attachments_phrase(0) == ""
    assert attachments_phrase(1) == ", с вложением"
    assert attachments_phrase(2) == ", с двумя вложениями"
    assert attachments_phrase(3) == ", с тремя вложениями"
    assert attachments_phrase(4) == ", с четырьмя вложениями"
    assert attachments_phrase(5) == ", с пятью вложениями"


# --- next_school_day ---

def test_next_school_day_skips_empty_days():
    sat = datetime.date(2026, 9, 19)
    sun = datetime.date(2026, 9, 20)
    mon = datetime.date(2026, 9, 21)
    diary = Diary(
        start=sat, end=mon,
        schedule=[
            Day(lessons=[], day=sun),
            Day(lessons=[_make_lesson(1, "А", [_make_assignment(1, "Домашнее задание", "x")])], day=mon),
        ],
    )
    assert next_school_day(diary, sat) == mon
    assert next_school_day(diary, mon) == mon


def test_next_school_day_none():
    sun = datetime.date(2026, 9, 20)
    diary = Diary(
        start=sun, end=sun + datetime.timedelta(days=2),
        schedule=[Day(lessons=[], day=sun), Day(lessons=[], day=sun + datetime.timedelta(days=1))],
    )
    assert next_school_day(diary, sun) is None


# --- collect_homework ---

def test_collect_homework_filters_non_homework():
    target = datetime.date(2026, 9, 21)
    lesson = _make_lesson(1, "Алгебра", [
        _make_assignment(1, "Домашнее задание", "Упр. 5"),
        _make_assignment(2, "Ответ на уроке", "---"),
    ])
    diary = _make_diary_for(target, [lesson])
    result = collect_homework(diary, target)
    assert len(result) == 1
    assert result[0]["subject"] == "Алгебра"
    assert result[0]["content"] == "Упр. 5"


def test_collect_homework_sorted_by_lesson_number():
    target = datetime.date(2026, 9, 21)
    l1 = _make_lesson(2, "Русский", [_make_assignment(2, "Домашнее задание", "Упр. 10")])
    l2 = _make_lesson(1, "Алгебра", [_make_assignment(1, "Домашнее задание", "Упр. 5")])
    diary = _make_diary_for(target, [l1, l2])
    result = collect_homework(diary, target)
    assert [r["subject"] for r in result] == ["Алгебра", "Русский"]


# --- format_for_voice ---

def test_format_for_voice_empty():
    assert format_for_voice([], datetime.date(2026, 9, 21)) == EMPTY_TEXT


def test_format_for_voice_single_item():
    target = datetime.date(2026, 9, 21)   # Monday
    today = datetime.date(2026, 9, 20)    # Sunday
    entries = [{"subject": "Алгебра", "content": "Упр. 5", "attachments": []}]
    text = format_for_voice(entries, target, today=today)
    assert text.startswith("На завтра, в понедельник, одно задание.")
    assert "Только алгебра: Упр. 5." in text
    assert text.endswith("Удачи с уроками!")


def test_format_for_voice_two_items():
    target = datetime.date(2026, 9, 21)
    today = datetime.date(2026, 9, 20)
    entries = [
        {"subject": "Алгебра", "content": "Упр. 5", "attachments": []},
        {"subject": "Русский язык", "content": "Упр. 10", "attachments": []},
    ]
    text = format_for_voice(entries, target, today=today)
    assert "два задания" in text
    assert "Первое — алгебра: Упр. 5." in text
    assert "Второе — русский язык: Упр. 10." in text


def test_format_for_voice_three_items_uses_connectors():
    target = datetime.date(2026, 9, 21)
    today = datetime.date(2026, 9, 20)
    entries = [
        {"subject": "Алгебра", "content": "Упр. 5", "attachments": []},
        {"subject": "Русский язык", "content": "Упр. 10", "attachments": []},
        {"subject": "Литература", "content": "Прочитать", "attachments": []},
    ]
    text = format_for_voice(entries, target, today=today, rng=random.Random(42))
    assert "три задания" in text
    assert "Первое — алгебра" in text
    assert "литература" in text
    # Middle and last connectors come from the fixed lists
    assert any(c in text for c in ["Теперь", "Дальше", "Потом", "Следующее"])
    assert any(c in text for c in ["И наконец —", "И последнее —"])


def test_format_for_voice_attachments():
    target = datetime.date(2026, 9, 21)
    today = datetime.date(2026, 9, 20)
    entries = [
        {"subject": "Литература", "content": "Прочитать", "attachments": ["file.docx"]},
    ]
    text = format_for_voice(entries, target, today=today)
    assert "с вложением" in text


def test_format_for_voice_five_attachments_instrumental():
    target = datetime.date(2026, 9, 21)
    today = datetime.date(2026, 9, 20)
    entries = [
        {"subject": "Литература", "content": "Прочитать", "attachments": [f"a{i}.docx" for i in range(5)]},
    ]
    text = format_for_voice(entries, target, today=today)
    assert "с пятью вложениями" in text


def test_format_for_voice_non_tomorrow_uses_na_weekday():
    # target = Wednesday, today = Monday (3 days ahead)
    target = datetime.date(2026, 9, 23)  # Wednesday
    today = datetime.date(2026, 9, 21)   # Monday
    entries = [{"subject": "Алгебра", "content": "Упр. 5", "attachments": []}]
    text = format_for_voice(entries, target, today=today)
    assert text.startswith("На среду, одно задание.")


# --- homework_entries ---

def test_homework_entries_builds_library_entries():
    from alice_skill.homework import homework_entries
    raw = [
        {"subject": "География", "content": "<p>параграф 6</p>", "assignment_id": 1},
        {"subject": "Биология", "content": "§ 3, вопросы", "assignment_id": 2},
    ]
    result = homework_entries(raw)
    assert [e.subject for e in result] == ["География", "Биология"]
    assert result[0].content == "параграф 6"
    assert result[1].content == "§ 3, вопросы"