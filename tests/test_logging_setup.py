import logging

from alice_skill import logging_setup


def _detach(handler):
    logging.getLogger().removeHandler(handler)
    handler.close()


def test_setup_logging_writes_to_file(tmp_path):
    log = tmp_path / "alice-homework.log"
    handler = logging_setup.setup_logging(log, max_bytes=10000, backup_count=1)
    try:
        logger = logging.getLogger("t_logging_setup")
        logger.setLevel(logging.INFO)
        logger.info("hello %d", 42)
        handler.flush()
        assert log.exists()
        assert "hello 42" in log.read_text(encoding="utf-8")
    finally:
        _detach(handler)


def test_setup_logging_rotates_at_limit(tmp_path):
    log = tmp_path / "alice-homework.log"
    handler = logging_setup.setup_logging(log, max_bytes=900, backup_count=1)
    try:
        chunk = "x" * 300
        logger = logging.getLogger("t_logging_setup_rot")
        logger.setLevel(logging.INFO)
        for _ in range(30):
            logger.info("%s", chunk)
        handler.flush()
        archive = tmp_path / "alice-homework.log.1"
        assert archive.exists()
        assert log.stat().st_size <= 4000
    finally:
        _detach(handler)