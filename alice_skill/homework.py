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
        if day.day >= start and day.lessons:
            return day.day
    return None


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
        body = _clean_content(entry["content"])
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