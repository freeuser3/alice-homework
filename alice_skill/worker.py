from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable

from alice_skill.cache import HomeworkCache
from alice_skill.sgo import ERROR_TEXT, HomeworkResult

logger = logging.getLogger(__name__)


class PrefetchWorker:
    def __init__(
        self,
        fetch: Callable[[], Awaitable[HomeworkResult]],
        cache: HomeworkCache,
        interval: float,
    ) -> None:
        self._fetch = fetch
        self._cache = cache
        self._interval = interval
        self._task: asyncio.Task[None] | None = None
        self._running: bool = False

    async def start(self) -> None:
        await self._refresh_once()
        self._task = asyncio.create_task(self._loop())

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            await self._refresh_once()

    def refresh_now(self) -> None:
        """Fire-and-forget refresh; safe to call from handlers."""
        asyncio.create_task(self._refresh_once())

    async def _refresh_once(self) -> None:
        if self._running:
            return
        self._running = True
        try:
            result = await self._fetch()
        except Exception as exc:
            logger.exception("prefetch failed unexpectedly")
            result = HomeworkResult(
                status="error", target_date=None, text=ERROR_TEXT, error=str(exc),
            )
        finally:
            self._running = False
        self._cache.set(result)

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
