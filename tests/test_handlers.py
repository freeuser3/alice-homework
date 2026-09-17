import datetime
from unittest.mock import MagicMock

import pytest

from alice_skill.cache import HomeworkCache
from alice_skill.handlers.common import HINT_TEXT, PREMATURE_TEXT
from alice_skill.handlers.fallback import handle_fallback
from alice_skill.handlers.homework import handle_homework
from alice_skill.handlers.more import handle_more
from alice_skill.handlers.start import handle_start
from alice_skill.sgo import HomeworkResult
from alice_skill.worker import PrefetchWorker


def _ok_result(text: str = "На завтра одно задание.") -> HomeworkResult:
    return HomeworkResult(
        status="ok", target_date=datetime.date(2026, 9, 21), text=text,
    )


def _empty_result() -> HomeworkResult:
    return HomeworkResult(
        status="empty", target_date=None,
        text="На завтра ничего не задали. Можно отдыхать!",
    )


def _error_result() -> HomeworkResult:
    return HomeworkResult(
        status="error", target_date=None, text="error", error="boom",
    )


def _fake_message(command: str = "") -> MagicMock:
    msg = MagicMock()
    msg.command = command
    return msg


def _fake_cache(result) -> HomeworkCache:
    cache = HomeworkCache()
    if result is not None:
        cache.set(result)
    return cache


def _fake_worker() -> MagicMock:
    return MagicMock(spec=PrefetchWorker)


@pytest.mark.asyncio
async def test_start_handler_returns_homework_from_cache():
    cache = _fake_cache(_ok_result("На завтра математика."))
    worker = _fake_worker()
    result = await handle_start(_fake_message(), cache=cache, worker=worker)
    assert result.text == "На завтра математика."
    worker.refresh_now.assert_not_called()


@pytest.mark.asyncio
async def test_start_handler_premature_on_empty_cache():
    cache = _fake_cache(None)
    worker = _fake_worker()
    result = await handle_start(_fake_message(), cache=cache, worker=worker)
    assert result.text == PREMATURE_TEXT
    worker.refresh_now.assert_called_once()


@pytest.mark.asyncio
async def test_start_handler_empty_result_returns_empty_text():
    cache = _fake_cache(_empty_result())
    worker = _fake_worker()
    result = await handle_start(_fake_message(), cache=cache, worker=worker)
    assert "отдыхать" in result.text


@pytest.mark.asyncio
async def test_start_handler_error_result_premature():
    cache = _fake_cache(_error_result())
    worker = _fake_worker()
    result = await handle_start(_fake_message(), cache=cache, worker=worker)
    assert result.text == PREMATURE_TEXT
    worker.refresh_now.assert_called_once()


@pytest.mark.asyncio
async def test_homework_handler_ok():
    cache = _fake_cache(_ok_result())
    worker = _fake_worker()
    result = await handle_homework(
        _fake_message("что задали"), cache=cache, worker=worker,
    )
    assert "задание" in result.text


@pytest.mark.asyncio
async def test_homework_handler_premature():
    cache = _fake_cache(None)
    worker = _fake_worker()
    result = await handle_homework(_fake_message("дз"), cache=cache, worker=worker)
    assert result.text == PREMATURE_TEXT


@pytest.mark.asyncio
async def test_more_handler_returns_result():
    cache = _fake_cache(_ok_result("cached text"))
    result = await handle_more(_fake_message("дальше"), cache=cache)
    assert result.text == "cached text"


@pytest.mark.asyncio
async def test_more_handler_hint_when_empty():
    cache = _fake_cache(None)
    result = await handle_more(_fake_message("дальше"), cache=cache)
    assert result.text == HINT_TEXT


@pytest.mark.asyncio
async def test_more_handler_error_result_serves_cached_error_text():
    cache = _fake_cache(_error_result())
    result = await handle_more(_fake_message("дальше"), cache=cache)
    assert result.text == "error"


@pytest.mark.asyncio
async def test_fallback_handler():
    result = await handle_fallback(_fake_message("привет"))
    assert result.text == HINT_TEXT
