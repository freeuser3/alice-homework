from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from typing import Literal

from alice_skill.homework import (
    EMPTY_TEXT,
    collect_homework,
    format_for_voice,
    next_school_day,
)
from netschoolapi_plus import NetSchoolAPI

SGO_URL = "https://sgo.e-mordovia.ru"
ERROR_TEXT = "Не получилось заглянуть в дневник. Попробуй, пожалуйста, ещё раз чуть позже."

logger = logging.getLogger(__name__)


@dataclass
class HomeworkResult:
    status: Literal["ok", "empty", "error"]
    target_date: datetime.date | None
    text: str
    error: str | None = None


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
        diary = await ns.diary(start=target, end=target + datetime.timedelta(days=7))
        day = next_school_day(diary, target)
        if day is None:
            return HomeworkResult(status="empty", target_date=None, text=EMPTY_TEXT)
        entries = collect_homework(diary, day)
        for entry in entries:
            entry["attachments"] = await _assignment_attachment_names(
                ns, entry["assignment_id"]
            )
        text = format_for_voice(entries, day, today=today)
        status = "ok" if entries else "empty"
        return HomeworkResult(status=status, target_date=day, text=text)
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