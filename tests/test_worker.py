import asyncio
import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from alice_skill.cache import HomeworkCache
from alice_skill.sgo import ERROR_TEXT, HomeworkResult
from alice_skill.worker import PrefetchWorker


def _ok_result() -> HomeworkResult:
    return HomeworkResult(
        status="ok",
        target_date=datetime.date(2026, 9, 21),
        text="homework",
    )


@pytest.mark.asyncio
async def test_start_runs_fetch_once_and_sets_cache():
    cache = HomeworkCache()
    fetch = AsyncMock(return_value=_ok_result())
    worker = PrefetchWorker(fetch=fetch, cache=cache, interval=86400)

    await worker.start()
    await asyncio.sleep(0)
    assert cache.get() is not None
    assert cache.get().text == "homework"
    fetch.assert_awaited_once()
    await worker.stop()


@pytest.mark.asyncio
async def test_refresh_now_spawns_background_task():
    cache = HomeworkCache()
    fetch = AsyncMock(return_value=_ok_result())
    worker = PrefetchWorker(fetch=fetch, cache=cache, interval=86400)

    await worker.start()
    await asyncio.sleep(0)

    fetch.reset_mock()
    worker.refresh_now()
    await asyncio.sleep(0)
    assert fetch.await_count == 1

    await worker.stop()


@pytest.mark.asyncio
async def test_stop_cancels_loop():
    cache = HomeworkCache()
    fetch = AsyncMock(return_value=_ok_result())
    worker = PrefetchWorker(fetch=fetch, cache=cache, interval=0.01)

    await worker.start()
    await asyncio.sleep(0.05)
    await worker.stop()
    assert worker._task is not None
    assert worker._task.cancelled()


@pytest.mark.asyncio
async def test_fetch_error_sets_error_result_in_cache():
    cache = HomeworkCache()
    fetch = AsyncMock(side_effect=RuntimeError("network down"))
    worker = PrefetchWorker(fetch=fetch, cache=cache, interval=86400)

    await worker.start()
    await asyncio.sleep(0)

    result = cache.get()
    assert result is not None
    assert result.status == "error"
    assert result.text == ERROR_TEXT
    await worker.stop()


@pytest.mark.asyncio
async def test_concurrent_refresh_once_blocked():
    cache = HomeworkCache()
    call_count = 0

    async def slow_fetch():
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)
        return _ok_result()

    worker = PrefetchWorker(fetch=slow_fetch, cache=cache, interval=86400)
    await worker.start()
    worker.refresh_now()
    await asyncio.sleep(0.05)
    worker.refresh_now()
    await asyncio.sleep(0.2)
    assert call_count == 2
    await worker.stop()
