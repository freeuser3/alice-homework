from __future__ import annotations

import datetime
from dataclasses import dataclass

from alice_skill.sgo import HomeworkResult


@dataclass
class HomeworkCache:
    _result: HomeworkResult | None = None
    _fetched_at: datetime.datetime | None = None

    def get(self) -> HomeworkResult | None:
        return self._result

    def set(self, result: HomeworkResult) -> None:
        self._result = result
        self._fetched_at = datetime.datetime.now(tz=datetime.timezone.utc)

    def is_stale(self, ttl: datetime.timedelta) -> bool:
        if self._result is None or self._fetched_at is None:
            return True
        return (
            datetime.datetime.now(tz=datetime.timezone.utc) - self._fetched_at > ttl
        )
