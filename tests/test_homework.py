import datetime
import random

from alice_skill.homework import (
    EMPTY_TEXT,
    attachments_phrase,
    collect_homework,
    collect_lessons,
    collect_marks,
    collect_week_facts,
    collect_week_marks,
    collect_week_schedule,
    format_for_voice,
    format_lessons_for_voice,
    format_marks,
    next_school_day,
    number_to_words,
    number_to_words_feminine,
    number_to_words_instrumental,
    plural_count,
    summarize_context,
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


def test_next_school_day_skips_saturday_even_with_lessons():
    # 2026-09-19 — суббота; в расписании есть уроки, но в субботу не учатся
    sat = datetime.date(2026, 9, 19)
    mon = datetime.date(2026, 9, 21)
    diary = Diary(
        start=sat, end=mon,
        schedule=[
            Day(lessons=[_make_lesson(1, "Физкультура", [])], day=sat),
            Day(lessons=[_make_lesson(1, "А", [_make_assignment(1, "Домашнее задание", "x")])], day=mon),
        ],
    )
    assert next_school_day(diary, sat) == mon


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
    assert "Только алгебра: Упражнение 5." in text
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
    assert "Первое — алгебра: Упражнение 5." in text
    assert "Второе — русский язык: Упражнение 10." in text


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


def test_format_for_voice_expands_upr_abbreviation():
    target = datetime.date(2026, 9, 21)
    today = datetime.date(2026, 9, 20)
    entries = [{"subject": "Русский", "content": "упр.43", "attachments": []}]
    text = format_for_voice(entries, target, today=today)
    assert "упражнение 43" in text
    assert "упр." not in text


def test_format_for_voice_expands_upr_with_space_and_uppercase():
    target = datetime.date(2026, 9, 21)
    today = datetime.date(2026, 9, 20)
    entries = [
        {"subject": "Алгебра", "content": "Упр. 5", "attachments": []},
        {"subject": "Физика", "content": "упр. 10", "attachments": []},
    ]
    text = format_for_voice(entries, target, today=today)
    assert "Упражнение 5" in text
    assert "упражнение 10" in text
    assert "упр." not in text


def test_format_for_voice_keeps_other_text_unchanged():
    target = datetime.date(2026, 9, 21)
    today = datetime.date(2026, 9, 20)
    entries = [{"subject": "Алгебра", "content": "Сириус, урок 12, Задание 1 (а)", "attachments": []}]
    text = format_for_voice(entries, target, today=today)
    assert "Сириус, урок 12, Задание 1 (а)" in text


# --- collect_lessons / format_lessons_for_voice ---

def test_collect_lessons_orders_by_number_returns_first():
    target = datetime.date(2026, 9, 21)
    l0 = _make_lesson(0, "Классный час", [_make_assignment(1, "Домашнее задание", "x")])
    l1 = _make_lesson(1, "Алгебра", [_make_assignment(2, "Домашнее задание", "y")])
    l2 = _make_lesson(2, "Русский", [_make_assignment(3, "Домашнее задание", "z")])
    diary = _make_diary_for(target, [l2, l0, l1])
    lessons, first = collect_lessons(diary, target)
    assert lessons == ["Классный час", "Алгебра", "Русский"]
    assert first == 0


def test_collect_lessons_empty_day():
    diary = _make_diary_for(datetime.date(2026, 9, 21), [])
    lessons, first = collect_lessons(diary, datetime.date(2026, 9, 21))
    assert lessons == []
    assert first is None


def test_format_lessons_for_voice_zero_lesson():
    target = datetime.date(2026, 9, 21)   # Monday
    today = datetime.date(2026, 9, 20)    # Sunday
    text = format_lessons_for_voice(["Классный час", "Алгебра"], 0, target, today=today)
    assert text == "На завтра, в понедельник, уроки с нулевого: классный час, алгебра."


def test_format_lessons_for_voice_first_lesson():
    target = datetime.date(2026, 9, 21)
    today = datetime.date(2026, 9, 20)
    text = format_lessons_for_voice(["Алгебра", "Русский язык"], 1, target, today=today)
    assert text == "На завтра, в понедельник, уроки с первого: алгебра, русский язык."


def test_format_lessons_for_voice_not_tomorrow():
    target = datetime.date(2026, 9, 23)   # Wednesday
    today = datetime.date(2026, 9, 21)    # Monday (3 days ahead)
    text = format_lessons_for_voice(["Физика"], 1, target, today=today)
    assert text == "Завтра не учебный день. На среду, уроки с первого: физика."


def test_format_lessons_for_voice_tomorrow_no_warning():
    target = datetime.date(2026, 9, 22)   # Tuesday
    today = datetime.date(2026, 9, 21)    # Monday
    text = format_lessons_for_voice(["Физика"], 1, target, today=today)
    assert not text.startswith("Завтра не учебный день")
    assert text.startswith("На завтра,")


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


# --- number_to_words_feminine ---

def test_number_to_words_feminine():
    assert number_to_words_feminine(0) == "ноль"
    assert number_to_words_feminine(1) == "одна"
    assert number_to_words_feminine(2) == "две"
    assert number_to_words_feminine(5) == "пять"
    assert number_to_words_feminine(11) == "одиннадцать"
    assert number_to_words_feminine(21) == "двадцать одна"
    assert number_to_words_feminine(22) == "двадцать две"
    assert number_to_words_feminine(35) == "тридцать пять"


# --- collect_marks / format_marks ---

def _make_marked_assignment(aid: int, mark: int | None) -> Assignment:
    return Assignment(
        id=aid, comment="", type="Ответ на уроке", content="",
        mark=mark, is_duty=False, deadline=datetime.time(23, 59),
    )


def test_collect_marks_groups_by_mark_and_subject():
    monday = datetime.date(2026, 9, 21)  # Monday
    day = Day(
        lessons=[
            _make_lesson(1, "Алгебра", [
                _make_marked_assignment(1, 2),
                _make_marked_assignment(2, 3),
            ]),
            _make_lesson(2, "Химия", [
                _make_marked_assignment(3, 2),
            ]),
        ],
        day=monday,
    )
    diary = Diary(start=monday, end=monday + datetime.timedelta(days=7), schedule=[day])
    marks = collect_marks(diary)
    assert marks == {2: {"Алгебра": 1, "Химия": 1}, 3: {"Алгебра": 1}}


def test_collect_marks_ignores_unmarked_assignments():
    monday = datetime.date(2026, 9, 21)
    day = Day(
        lessons=[
            _make_lesson(1, "Алгебра", [
                _make_marked_assignment(1, 2),
                _make_marked_assignment(2, None),
                _make_marked_assignment(3, 0),
            ]),
        ],
        day=monday,
    )
    diary = Diary(start=monday, end=monday + datetime.timedelta(days=7), schedule=[day])
    marks = collect_marks(diary)
    assert marks == {2: {"Алгебра": 1}}


def test_format_marks_zero():
    assert format_marks(2, {}) == "Двоек за неделю нет."
    assert format_marks(5, {}) == "Пятёрок за неделю нет."


def test_format_marks_single_subject():
    text = format_marks(2, {"Химия": 2})
    assert text == "За неделю две двойки: химия — 2."


def test_format_marks_multiple_subjects():
    text = format_marks(3, {"Химия": 1, "Алгебра": 1})
    assert text == "За неделю две тройки: алгебра, химия."


def test_format_marks_counts_per_subject():
    text = format_marks(4, {"Химия": 2, "Алгебра": 1})
    assert text == "За неделю три четвёрки: алгебра, химия — 2."


def test_format_marks_many_marks():
    text = format_marks(2, {"Химия": 5})
    assert text == "За неделю пять двоек: химия — 5."


def test_format_marks_single_total():
    text = format_marks(5, {"Биология": 1})
    assert text == "За неделю одна пятёрка: биология."


# --- collect_week_schedule / collect_week_marks / summarize_context ---

def _marked(mark: int, comment: str = "") -> Assignment:
    return Assignment(
        id=mark, comment=comment, type="Ответ на уроке", content="",
        mark=mark, is_duty=False, deadline=datetime.date(2026, 9, 21),
    )


def _week_diary() -> Diary:
    monday = datetime.date(2026, 9, 21)  # Monday of week
    tuesday = datetime.date(2026, 9, 22)  # Tuesday
    sunday = datetime.date(2026, 9, 27)   # Sunday (should be ignored)
    days = [
        Day(lessons=[
            _make_lesson(1, "Алгебра", [_marked(5, "Отлично")]),
            _make_lesson(2, "Химия", [_marked(4)]),
        ], day=monday),
        Day(lessons=[
            _make_lesson(1, "Физика", [_marked(3), _marked(4)]),
        ], day=tuesday),
        Day(lessons=[_make_lesson(1, "Физкультура", [_marked(2)])], day=sunday),
    ]
    return Diary(start=monday, end=tuesday, schedule=days)


def test_collect_week_schedule_groups_by_day():
    monday = datetime.date(2026, 9, 21)
    result = collect_week_schedule(_week_diary(), monday)
    assert result["2026-09-21"] == ["Алгебра", "Химия"]
    assert result["2026-09-22"] == ["Физика"]
    assert "2026-09-27" not in result


def test_collect_week_schedule_ignores_days_before_monday():
    monday = datetime.date(2026, 9, 21)
    prev_sunday = datetime.date(2026, 9, 20)
    diary = Diary(
        start=prev_sunday, end=prev_sunday + datetime.timedelta(days=7),
        schedule=[Day(lessons=[_make_lesson(1, "Старая", [])], day=prev_sunday)],
    )
    assert collect_week_schedule(diary, monday) == {}


def test_collect_week_marks_with_comments():
    monday = datetime.date(2026, 9, 21)
    marks = collect_week_marks(_week_diary(), monday)
    assert marks == [
        {"day": "2026-09-21", "subject": "Алгебра", "mark": 5, "comment": "Отлично"},
        {"day": "2026-09-21", "subject": "Химия", "mark": 4, "comment": ""},
        {"day": "2026-09-22", "subject": "Физика", "mark": 3, "comment": ""},
        {"day": "2026-09-22", "subject": "Физика", "mark": 4, "comment": ""},
    ]


def test_collect_week_marks_ignores_unmarked_and_duty():
    monday = datetime.date(2026, 9, 21)
    duty = Assignment(
        id=99, comment="", type="Ответ на уроке", content="",
        mark=5, is_duty=True, deadline=datetime.date(2026, 9, 21),
    )
    none_mark = Assignment(
        id=100, comment="", type="Ответ на уроке", content="",
        mark=None, is_duty=False, deadline=datetime.date(2026, 9, 21),
    )
    day = Day(lessons=[_make_lesson(1, "Алгебра", [duty, none_mark])], day=monday)
    diary = Diary(start=monday, end=monday + datetime.timedelta(days=7), schedule=[day])
    assert collect_week_marks(diary, monday) == []


def test_summarize_context_sections():
    today = datetime.date(2026, 9, 21)   # Monday
    target = datetime.date(2026, 9, 22)  # Tuesday (tomorrow)
    schedule = {"2026-09-21": ["Алгебра", "Химия"]}
    marks = [{"day": "2026-09-21", "subject": "Алгебра", "mark": 5, "comment": "Отлично"},
             {"day": "2026-09-21", "subject": "Химия", "mark": 4, "comment": ""},
             {"day": "2026-09-21", "subject": "Химия", "mark": 4, "comment": ""}]
    text = summarize_context(schedule, marks, [], ["Физика"], [("Алгебра", "Упр. 5")], target, today)
    assert "Неделя: 2026-09-21 — 2026-09-27" in text
    assert "Расписание за неделю:" in text
    assert "понедельник 21.09: Алгебра, Химия" in text
    assert "Оценки за неделю:" in text
    assert "2026-09-21 Алгебра: 5. Комментарий: Отлично" in text
    assert "2026-09-21 Химия: 4" in text
    assert "Средний балл по предметам:" in text
    assert "Алгебра: 5.0 (1 оценок)" in text
    assert "Химия: 4.0 (2 оценок)" in text
    assert "Просроченные задания:" in text
    assert "Уроки на завтра" in text
    assert "Физика" in text
    assert "Домашнее задание на завтра" in text
    assert "Алгебра: Упр. 5" in text


def test_summarize_context_says_tomorrow_only_when_target_is_tomorrow():
    today = datetime.date(2026, 9, 21)   # Monday
    target = datetime.date(2026, 9, 22)  # Tuesday, именно завтра
    text = summarize_context({"2026-09-21": ["Алгебра"]}, [],
                             [], ["Физика"], [("Алгебра", "Упр. 5")], target, today)
    assert "Уроки на завтра, вторник 22.09:" in text
    assert "Домашнее задание на завтра, вторник 22.09:" in text
    # после выходных target = понедельник, «завтра» больше не используется
    friday = datetime.date(2026, 9, 25)
    monday = datetime.date(2026, 9, 28)
    text = summarize_context({"2026-09-28": ["Физика"]}, [],
                             [], ["Физика"], [("Алгебра", "Упр. 5")], monday, friday)
    assert "Уроки на завтра" not in text
    assert "Домашнее задание на завтра" not in text
    assert "Уроки на понедельник 28.09:" in text
    assert "Домашнее задание на понедельник 28.09:" in text


def test_summarize_context_empty():
    today = datetime.date(2026, 9, 21)
    target = datetime.date(2026, 9, 22)
    text = summarize_context({}, [], [], ["Физика"], [], target, today)
    assert "уроков не было" in text
    assert "оценок нет" in text
    assert "нет данных" in text
    assert "Уроки на завтра" in text
    assert "Физика" in text
    assert "Домашнее задание на завтра" in text
    assert "не задано" in text


def test_summarize_context_overdue_section():
    today = datetime.date(2026, 9, 21)
    target = datetime.date(2026, 9, 22)
    overdue = [{"content": "Параграф 3", "deadline": "2026-09-18"}]
    text = summarize_context({}, [], overdue, [], [], target, today)
    assert "Параграф 3 до 2026-09-18" in text


# --- collect_week_facts / summarize_context with memory ---

def test_collect_week_facts_averages_and_buckets():
    marks = [
        {"day": "2026-09-21", "subject": "Алгебра", "mark": 5, "comment": ""},
        {"day": "2026-09-21", "subject": "Алгебра", "mark": 4, "comment": ""},
        {"day": "2026-09-22", "subject": "Химия", "mark": 3, "comment": ""},
        {"day": "2026-09-22", "subject": "Физика", "mark": 5, "comment": ""},
    ]
    overdue = [{"content": "Параграф", "deadline": "2026-09-18"}]
    facts = collect_week_facts(marks, overdue)
    assert facts["marks_count"] == 4
    assert facts["avg"] == 4.2
    assert facts["strong"] == ["Алгебра", "Физика"]
    assert facts["weak"] == ["Химия"]
    assert facts["overdue"] == 1


def test_collect_week_facts_empty():
    facts = collect_week_facts([], [])
    assert facts["marks_count"] == 0
    assert facts["avg"] is None
    assert facts["strong"] == []
    assert facts["weak"] == []
    assert facts["overdue"] == 0


def test_summarize_context_omits_memory_when_empty():
    today = datetime.date(2026, 9, 21)
    target = datetime.date(2026, 9, 22)
    text = summarize_context({}, [], [], [], [], target, today)
    assert "Память о прошлых неделях" not in text


def test_summarize_context_appends_memory_context():
    today = datetime.date(2026, 9, 21)
    target = datetime.date(2026, 9, 22)
    memory = "Дайджест прошлых недель: алгебра растёт"
    text = summarize_context({}, [], [], [], [], target, today, memory_context=memory)
    assert "Память о прошлых неделях" in text
    assert "Дайджест прошлых недель: алгебра растёт" in text