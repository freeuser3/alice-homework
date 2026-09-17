import datetime
from datetime import timedelta

from alice_skill.cache import HomeworkCache
from alice_skill.sgo import HomeworkResult


def _ok_result(text: str = "homework text") -> HomeworkResult:
    return HomeworkResult(
        status="ok", target_date=datetime.date(2026, 9, 21), text=text,
    )


def _error_result() -> HomeworkResult:
    return HomeworkResult(
        status="error", target_date=None, text="error", error="boom",
    )


def test_get_returns_none_initially():
    cache = HomeworkCache()
    assert cache.get() is None


def test_set_and_get():
    cache = HomeworkCache()
    result = _ok_result("На завтра одно задание.")
    cache.set(result)
    assert cache.get() is result
    assert cache.get().text == "На завтра одно задание."


def test_overwrite():
    cache = HomeworkCache()
    r1 = _ok_result("first")
    r2 = _ok_result("second")
    cache.set(r1)
    cache.set(r2)
    assert cache.get() is r2


def test_stale_when_empty():
    cache = HomeworkCache()
    assert cache.is_stale(timedelta(minutes=30)) is True


def test_not_stale_immediately_after_set():
    cache = HomeworkCache()
    cache.set(_ok_result())
    assert cache.is_stale(timedelta(hours=1)) is False


def test_stale_after_ttl():
    cache = HomeworkCache()
    cache.set(_ok_result())
    # Rewind the timestamp to simulate an old fetch
    cache._fetched_at = datetime.datetime.now(
        tz=datetime.timezone.utc,
    ) - timedelta(hours=2)
    assert cache.is_stale(timedelta(hours=1)) is True


def test_error_result_in_cache():
    cache = HomeworkCache()
    cache.set(_error_result())
    assert cache.get().status == "error"
    assert cache.is_stale(timedelta(minutes=5)) is False
