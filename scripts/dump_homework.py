"""Dump all homework entries for a date range from the SGO diary.

Usage (on the skill server, inside the skill's venv):

    python scripts/dump_homework.py            # today-7 .. today+7
    python scripts/dump_homework.py 2026-09-14 2026-09-28

Prints "subject: content" per line (HTML stripped), grouped by day and lesson,
so we can see how teachers actually word their homework.
"""
from __future__ import annotations

import asyncio
import datetime
import re
import sys

from alice_skill.config import load_config
from alice_skill.homework import HOMEWORK_TYPE, collect_homework, next_school_day
from netschoolapi_plus import NetSchoolAPI

SGO_URL = "https://sgo.e-mordovia.ru"


def _clean(content: str) -> str:
    text = re.sub(r"<[^>]+>", " ", content)
    return re.sub(r"\s+", " ", text).strip()


async def dump(start: datetime.date, end: datetime.date) -> None:
    cfg = load_config()
    ns = NetSchoolAPI(SGO_URL, default_requests_timeout=None)
    try:
        await ns.login(cfg.sgo.login, cfg.sgo.password, cfg.sgo.school)
        diary = await ns.diary(start=start, end=end)
        found = 0
        for day in sorted(diary.schedule, key=lambda d: d.day):
            entries = collect_homework(diary, day.day)
            if not entries:
                continue
            print(f"\n=== {day.day.isoformat()} ===")
            for e in entries:
                content = _clean(e["content"])
                if content:
                    print(f"  [{e['subject']}] {content}")
                    found += 1
        if not found:
            print("No homework entries in range.")
    finally:
        try:
            await ns.logout()
        except Exception:
            pass


def main() -> None:
    if len(sys.argv) == 3:
        start = datetime.date.fromisoformat(sys.argv[1])
        end = datetime.date.fromisoformat(sys.argv[2])
    else:
        today = datetime.date.today()
        start = today - datetime.timedelta(days=7)
        end = today + datetime.timedelta(days=7)
    asyncio.run(dump(start, end))


if __name__ == "__main__":
    main()
