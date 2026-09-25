import logging
from types import SimpleNamespace

import pytest
from aliceio.types import Response

from alice_skill.logging_middleware import LoggingMiddleware


def _event():
    req = SimpleNamespace(
        type="SimpleUtterance",
        command="спроси по географии",
        original_utterance="расспроси про горы",
    )
    session = SimpleNamespace(
        session_id="sid-x",
        message_id=7,
        new=False,
        application=SimpleNamespace(application_id="app-1"),
    )
    return SimpleNamespace(request=req, session=session)


@pytest.mark.asyncio
async def test_logs_command_original_and_response(caplog):
    async def handler(event, data):
        return Response(text="Ответ навыка")

    with caplog.at_level(logging.INFO, logger="alice_skill.logging_middleware"):
        await LoggingMiddleware()(handler, _event(), {})

    record = next(r for r in caplog.records if r.message.startswith("alice update"))
    assert "sid=sid-x" in record.message
    assert "new=False" in record.message
    assert "app=app-1" in record.message
    assert "command='спроси по географии'" in record.message
    assert "original='расспроси про горы'" in record.message
    assert "response='Ответ навыка'" in record.message
    assert "ms=" in record.message


@pytest.mark.asyncio
async def test_logs_exception_and_reraises(caplog):
    async def handler(event, data):
        raise RuntimeError("boom")

    with caplog.at_level(logging.INFO, logger="alice_skill.logging_middleware"):
        with pytest.raises(RuntimeError):
            await LoggingMiddleware()(handler, _event(), {})
    assert any(r.levelno == logging.ERROR for r in caplog.records)