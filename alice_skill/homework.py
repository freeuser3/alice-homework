from __future__ import annotations

import datetime
import random
import re
from typing import Optional

from netschoolapi_plus.schemas import Diary
from quiz_library.model import HomeworkEntry

HOMEWORK_TYPE = "Домашнее задание"
EMPTY_TEXT = "На завтра ничего не задали. Можно отдыхать!"
CLOSING = "Удачи с уроками"
DAYOFF_WEEKDAY = 5  # суббота — день без занятий

_UNITS = [
    None, "одно", "два", "три", "четыре", "пять",
    "шесть", "семь", "восемь", "девять",
]
_TEENS = [
    "десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать",
    "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать",
]
_TENS = [
    None, None, "двадцать", "тридцать", "сорок", "пятьдесят",
    "шестьдесят", "семьдесят", "восемьдесят", "девяносто",
]

# Instrumental case (творительный падеж) for "с N вложениями"
_INSTRUMENTAL_UNITS = [
    None, "одним", "двумя", "тремя", "четырьмя", "пятью",
    "шестью", "семью", "восемью", "девятью",
]
_INSTRUMENTAL_TEENS = [
    "десятью", "одиннадцатью", "двенадцатью", "тринадцатью", "четырнадцатью",
    "пятнадцатью", "шестнадцатью", "семнадцатью", "восемнадцатью", "девятнадцатью",
]
_INSTRUMENTAL_TENS = [
    None, None, "двадцатью", "тридцатью", "сорока", "пятьюдесятью",
    "шестьюдесятью", "семьюдесятью", "восемьюдесятью", "девяноста",
]

_WEEKDAY_ACC = [
    "понедельник", "вторник", "среду", "четверг",
    "пятницу", "субботу", "воскресенье",
]
_WEEKDAY_PREP = [
    "в понедельник", "во вторник", "в среду", "в четверг",
    "в пятницу", "в субботу", "в воскресенье",
]

MIDDLE_CONNECTORS = ["Теперь", "Дальше", "Потом", "Следующее"]
LAST_CONNECTORS = ["И наконец —", "И последнее —"]


def number_to_words(n: int) -> str:
    if n == 0:
        return "ноль"
    if 1 <= n <= 9:
        return _UNITS[n]
    if 10 <= n <= 19:
        return _TEENS[n - 10]
    if 20 <= n <= 99:
        tens, units = divmod(n, 10)
        if units == 0:
            return _TENS[tens]
        unit_word = "одно" if units == 1 else _UNITS[units]
        return f"{_TENS[tens]} {unit_word}"
    return str(n)


_FEMININE_UNITS = [
    None, "одна", "две", "три", "четыре", "пять",
    "шесть", "семь", "восемь", "девять",
]


def number_to_words_feminine(n: int) -> str:
    if n == 0:
        return "ноль"
    if 1 <= n <= 9:
        return _FEMININE_UNITS[n]
    if 10 <= n <= 19:
        return _TEENS[n - 10]
    if 20 <= n <= 99:
        tens, units = divmod(n, 10)
        if units == 0:
            return _TENS[tens]
        unit_word = "одна" if units == 1 else _FEMININE_UNITS[units]
        return f"{_TENS[tens]} {unit_word}"
    return str(n)


def number_to_words_instrumental(n: int) -> str:
    if 1 <= n <= 9:
        return _INSTRUMENTAL_UNITS[n]
    if 10 <= n <= 19:
        return _INSTRUMENTAL_TEENS[n - 10]
    if 20 <= n <= 99:
        tens, units = divmod(n, 10)
        if units == 0:
            return _INSTRUMENTAL_TENS[tens]
        unit_word = "одним" if units == 1 else _INSTRUMENTAL_UNITS[units]
        return f"{_INSTRUMENTAL_TENS[tens]} {unit_word}"
    return str(n)


def plural_count(n: int) -> str:
    n100 = n % 100
    n10 = n % 10
    if 11 <= n100 <= 19:
        return "заданий"
    if n10 == 1:
        return "задание"
    if 2 <= n10 <= 4:
        return "задания"
    return "заданий"


def attachments_phrase(n: int) -> str:
    if n == 0:
        return ""
    if n == 1:
        return ", с вложением"
    if n == 2:
        return ", с двумя вложениями"
    return f", с {number_to_words_instrumental(n)} вложениями"


def _clean_content(content: str) -> str:
    text = re.sub(r"<[^>]+>", " ", content)
    text = re.sub(r"\s+", " ", text).strip()
    return text


_UPR_RE = re.compile(r"\b[Уу]пр\.")


def expand_abbreviations(text: str) -> str:
    def _expand(match: re.Match) -> str:
        return "Упражнение" if match.group(0).startswith("У") else "упражнение"

    # «упр.43» -> «упражнение 43» (без пробела перед номером)
    text = re.sub(r"\b[Уу]пр\.(?=\d)", lambda m: _expand(m) + " ", text)
    return _UPR_RE.sub(_expand, text)


def homework_entries(entries: list[dict]) -> list[HomeworkEntry]:
    return [
        HomeworkEntry(subject=e["subject"], content=_clean_content(e["content"]))
        for e in entries
    ]


def _opener(target: datetime.date, today: datetime.date) -> str:
    if target == today + datetime.timedelta(days=1):
        return "На завтра, " + _WEEKDAY_PREP[target.weekday()]
    return "На " + _WEEKDAY_ACC[target.weekday()]


def next_school_day(diary: Diary, start: datetime.date) -> Optional[datetime.date]:
    for day in sorted(diary.schedule, key=lambda d: d.day):
        if (
            day.day >= start
            and day.lessons
            and day.day.weekday() != DAYOFF_WEEKDAY
        ):
            return day.day
    return None


def collect_lessons(diary: Diary, target: datetime.date) -> tuple[list[str], Optional[int]]:
    for day in diary.schedule:
        if day.day == target:
            lessons = sorted(day.lessons, key=lambda l: l.number)
            first = lessons[0].number if lessons else None
            return [l.subject for l in lessons], first
    return [], None


def collect_homework(diary: Diary, target: datetime.date) -> list[dict]:
    result: list[dict] = []
    for day in diary.schedule:
        if day.day != target:
            continue
        for lesson in sorted(day.lessons, key=lambda l: l.number):
            for assignment in lesson.assignments:
                if assignment.type == HOMEWORK_TYPE:
                    result.append({
                        "day": day.day,
                        "number": lesson.number,
                        "subject": lesson.subject,
                        "content": assignment.content,
                        "assignment_id": assignment.id,
                        "attachments": [],
                    })
    return result


# Формы по падежам: (ед.ч. именительный, ед.ч. род.п. для 2–4, мн.ч. род.п. для 5+, 11–19)
_MARK_FORMS: dict[int, tuple[str, str, str]] = {
    2: ("двойка", "двойки", "двоек"),
    3: ("тройка", "тройки", "троек"),
    4: ("четвёрка", "четвёрки", "четвёрок"),
    5: ("пятёрка", "пятёрки", "пятёрок"),
}


def _mark_form(mark: int, n: int) -> str:
    singular, gen_singular, gen_plural = _MARK_FORMS[mark]
    n100 = n % 100
    n10 = n % 10
    if 11 <= n100 <= 19:
        return gen_plural
    if n10 == 1:
        return singular
    if 2 <= n10 <= 4:
        return gen_singular
    return gen_plural


def collect_marks(diary: Diary) -> dict[int, dict[str, int]]:
    """Собирает оценки из дневника: {балл: {предмет: количество}}."""
    result: dict[int, dict[str, int]] = {}
    for day in diary.schedule:
        for lesson in day.lessons:
            for assignment in lesson.assignments:
                if assignment.mark and not assignment.is_duty:
                    counts = result.setdefault(assignment.mark, {})
                    counts[lesson.subject] = counts.get(lesson.subject, 0) + 1
    return result


_DAY_EMOJI = {0: "Понедельник", 1: "Вторник", 2: "Среда", 3: "Четверг",
              4: "Пятница", 5: "Суббота", 6: "Воскресенье"}
_DAY_LBL = {0: "понедельник", 1: "вторник", 2: "среду", 3: "четверг",
            4: "пятницу", 5: "субботу", 6: "воскресенье"}


def collect_week_schedule(diary: Diary, monday: datetime.date) -> dict[str, list[str]]:
    """Предметы по дням недели: {день.isoformat(): [предметы]}."""
    result: dict[str, list[str]] = {}
    for day in diary.schedule:
        if day.day < monday or day.day.weekday() >= 6:
            continue
        lessons = sorted(day.lessons, key=lambda l: l.number)
        result[day.day.isoformat()] = [l.subject for l in lessons]
    return result


def collect_week_marks(diary: Diary, monday: datetime.date) -> list[dict]:
    """Оценки за неделю по дням: [{day, subject, mark, comment}] (кроме дежурных)."""
    result: list[dict] = []
    for day in diary.schedule:
        if day.day < monday or day.day.weekday() >= 6:
            continue
        for lesson in day.lessons:
            for assignment in lesson.assignments:
                if assignment.mark and not assignment.is_duty:
                    result.append({
                        "day": day.day.isoformat(),
                        "subject": lesson.subject,
                        "mark": assignment.mark,
                        "comment": assignment.comment or "",
                    })
    return result


def summarize_context(
    week_schedule: dict[str, list[str]],
    week_marks: list[dict],
    overdue: list[dict],
    tomorrow_lessons: list[str],
    tomorrow_homework: list[tuple[str, str]],
    target: datetime.date,
    today: datetime.date,
) -> str:
    """Строит текстовый контекст для LLM: расписание, оценки, долги, уроки на завтра."""
    lines: list[str] = []

    monday = today - datetime.timedelta(days=today.weekday())
    sunday = monday + datetime.timedelta(days=6)
    lines.append(f"Неделя: {monday.isoformat()} — {sunday.isoformat()}")
    lines.append("")

    lines.append("Расписание за неделю:")
    if not week_schedule:
        lines.append("  уроков не было")
    for day_iso in sorted(week_schedule):
        d = datetime.date.fromisoformat(day_iso)
        subjects = ", ".join(week_schedule[day_iso])
        lines.append(f"  {_DAY_LBL[d.weekday()]} {d.strftime('%d.%m')}: {subjects}")
    lines.append("")

    lines.append("Оценки за неделю:")
    if not week_marks:
        lines.append("  оценок нет")
    for m in sorted(week_marks, key=lambda x: x["day"]):
        comment = f". Комментарий: {m['comment']}" if m.get("comment") else ""
        lines.append(f"  {m['day']} {m['subject']}: {m['mark']}{comment}")
    lines.append("")

    lines.append("Средний балл по предметам:")
    avgs: dict[str, list[float]] = {}
    for m in week_marks:
        avgs.setdefault(m["subject"], []).append(m["mark"])
    if not avgs:
        lines.append("  нет данных")
    for subject in sorted(avgs):
        vals = avgs[subject]
        lines.append(f"  {subject}: {sum(vals) / len(vals):.1f} ({len(vals)} оценок)")
    lines.append("")

    lines.append("Просроченные задания:")
    if not overdue:
        lines.append("  нет")
    for item in overdue:
        deadline = f" до {item['deadline']}" if item.get("deadline") else ""
        lines.append(f"  {item['content']}{deadline}")
    lines.append("")

    lines.append(f"Уроки на завтра, "
                 f"{_DAY_LBL[target.weekday()]} {target.strftime('%d.%m')}:")
    if tomorrow_lessons:
        lines.append(f"  {', '.join(tomorrow_lessons)}")
    else:
        lines.append("  уроков нет")
    lines.append("")

    lines.append(f"Домашнее задание на завтра, "
                 f"{_DAY_LBL[target.weekday()]} {target.strftime('%d.%m')}:")
    if tomorrow_homework:
        for subject, content in tomorrow_homework:
            lines.append(f"  {subject}: {content}")
    else:
        lines.append("  не задано")
    lines.append("")

    return "\n".join(lines)


def format_marks(mark: int, counts: dict[str, int]) -> str:
    total = sum(counts.values())
    if total == 0:
        plural = _MARK_FORMS[mark][2]
        return f"{plural[0].upper() + plural[1:]} за неделю нет."
    parts = []
    for subject, cnt in sorted(counts.items()):
        if cnt == 1:
            parts.append(subject.lower())
        else:
            parts.append(f"{subject.lower()} — {cnt}")
    word = _mark_form(mark, total)
    return (
        f"За неделю {number_to_words_feminine(total)} {word}: "
        f"{', '.join(parts)}."
    )


def format_for_voice(
    entries: list[dict],
    target: datetime.date,
    today: datetime.date | None = None,
    rng: random.Random | None = None,
) -> str:
    if not entries:
        return EMPTY_TEXT
    today = today or datetime.date.today()
    rng = rng or random.Random()
    count = len(entries)
    count_phrase = f"{number_to_words(count)} {plural_count(count)}"
    opener = f"{_opener(target, today)}, {count_phrase}."
    parts: list[str] = [opener]
    for i, entry in enumerate(entries):
        subject = entry["subject"].lower()
        body = expand_abbreviations(_clean_content(entry["content"]))
        att_count = len(entry.get("attachments", []))
        body += attachments_phrase(att_count)
        if count == 1:
            prefix = "Только"
        elif i == 0:
            prefix = "Первое —"
        elif i == count - 1 and count >= 3:
            prefix = rng.choice(LAST_CONNECTORS)
        elif i == 1 and count == 2:
            prefix = "Второе —"
        else:
            prefix = rng.choice(MIDDLE_CONNECTORS)
        parts.append(f"{prefix} {subject}: {body}.")
    parts.append(f"{CLOSING}!")
    return " ".join(parts)


def format_lessons_for_voice(
    lessons: list[str],
    first: Optional[int],
    target: datetime.date,
    today: datetime.date | None = None,
) -> str:
    if not lessons:
        return EMPTY_TEXT
    today = today or datetime.date.today()
    opener = _opener(target, today)
    if target != today + datetime.timedelta(days=1):
        opener = "Завтра не учебный день. " + opener
    start_phrase = (
        "с нулевого" if first == 0
        else "с первого" if first == 1
        else f"с {first}-го"
    )
    body = ", ".join(l.lower() for l in lessons)
    return f"{opener}, уроки {start_phrase}: {body}."