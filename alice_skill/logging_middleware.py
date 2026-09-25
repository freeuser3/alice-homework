"""Мидлварь логирования апдейтов Алисы: вход (запрос) и выход (ответ)."""
from __future__ import annotations

import logging
import time

from aliceio.types import Response, Update

logger = logging.getLogger(__name__)

MAX_RESPONSE_CHARS = 200


def _response_text(result) -> str:
    if isinstance(result, Response):
        return result.text or ""
    return ""


class LoggingMiddleware:
    async def __call__(self, handler, event: Update, data: dict) -> Response | None:
        req = event.request
        session = event.session
        sid = session.session_id
        mid = session.message_id
        new = session.new
        app = session.application.application_id
        t0 = time.monotonic()
        try:
            result = await handler(event, data)
        except Exception:
            logger.exception(
                "alice update ERROR: sid=%s mid=%s type=%s command=%r",
                sid, mid, req.type, req.command,
            )
            raise
        ms = (time.monotonic() - t0) * 1000.0
        logger.info(
            "alice update: sid=%s mid=%s new=%s app=%s type=%s ms=%d "
            "command=%r original=%r -> response=%r",
            sid, mid, new, app, req.type, int(ms),
            req.command, req.original_utterance,
            _response_text(result)[:MAX_RESPONSE_CHARS],
        )
        return result