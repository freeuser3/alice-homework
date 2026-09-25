from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass, field
from typing import Literal

from alice_skill.homework import (
    EMPTY_TEXT,
    collect_homework,
    collect_lessons,
    collect_marks,
    collect_week_marks,
    collect_week_schedule,
    format_for_voice,
    format_lessons_for_voice,
    homework_entries,
    next_school_day,
)
from netschoolapi_plus import NetSchoolAPI
from quiz_library.model import HomeworkEntry

SGO_URL = "https://sgo.e-mordovia.ru"
ERROR_TEXT = "Не получилось заглянуть в дневник. Попробуй, пожалуйста, ещё раз чуть позже."

logger = logging.getLogger(__name__)


@dataclass
class HomeworkResult:
    status: Literal["ok", "empty", "error"]
    target_date: datetime.date | None
    text: str
    error: str | None = None
    entries: list[HomeworkEntry] = field(default_factory=list)
    lessons: list[str] = field(default_factory=list)
    lessons_text: str = ""
    marks: dict[int, dict[str, int]] = field(default_factory=dict)
    week_schedule: dict[str, list[str]] = field(default_factory=dict)
    week_marks: list[dict] = field(default_factory=list)
    overdue: list[dict] = field(default_factory=list)


async def fetch_homework(
    login: str,
    password: str,
    school: str,
    *,
    url: str = SGO_URL,
    now: datetime.date | None = None,
) -> HomeworkResult:
    ns = NetSchoolAPI(url, default_requests_timeout=None)
    try:
        await ns.login(login, password, school)
        today = now or datetime.date.today()
        target = today + datetime.timedelta(days=1)
        start = today - datetime.timedelta(days=today.weekday())
        diary = await ns.diary(start=start, end=target + datetime.timedelta(days=7))
        day = next_school_day(diary, target)
        marks = collect_marks(diary)
        week_schedule = collect_week_schedule(diary, start)
        week_marks = collect_week_marks(diary, start)
        overdue = await _collect_overdue(ns, start, end=diary.end)
        if day is None:
            return HomeworkResult(
                status="empty", target_date=None, text=EMPTY_TEXT, marks=marks,
                week_schedule=week_schedule, week_marks=week_marks, overdue=overdue,
            )
        entries = collect_homework(diary, day)
        for entry in entries:
            entry["attachments"] = await _assignment_attachment_names(
                ns, entry["assignment_id"]
            )
        text = format_for_voice(entries, day, today=today)
        lessons, first_number = collect_lessons(diary, day)
        lessons_text = format_lessons_for_voice(lessons, first_number, day, today=today)
        status = "ok" if entries else "empty"
        return HomeworkResult(
            status=status, target_date=day, text=text,
            entries=homework_entries(entries),
            lessons=lessons, lessons_text=lessons_text,
            marks=marks,
            week_schedule=week_schedule, week_marks=week_marks, overdue=overdue,
        )
    except Exception as exc:
        logger.exception("fetch_homework failed")
        return HomeworkResult(
            status="error", target_date=None, text=ERROR_TEXT, error=str(exc),
        )
    finally:
        try:
            await ns.logout()
        except Exception:
            pass


async def _assignment_attachment_names(ns: NetSchoolAPI, assignment_id: int) -> list[str]:
    try:
        attachments = await ns.attachments(assignment_id)
    except Exception:
        return []
    return [a.name for a in attachments]


async def _collect_overdue(ns: NetSchoolAPI, start: datetime.date, end: datetime.date) -> list[dict]:
    try:
        assignments = await ns.overdue(start=start, end=end)
    except Exception:
        logger.exception("fetch overdue failed")
        return []
    result: list[dict] = []
    for assignment in assignments:
        content = (assignment.content or "").strip()
        if not content:
            continue
        result.append({
            "content": content,
            "deadline": assignment.deadline.isoformat() if assignment.deadline else "",
        })
    return result