from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aiohttp import web

from keenetic_skill.config import KeeneticConfig
from keenetic_skill.probe import redact, write_record

logger = logging.getLogger(__name__)

RESPONSE = {
    "response": {"text": "Записано", "end_session": False},
    "version": "1.0",
}


def _record(request: web.Request, body: Any) -> dict:
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "path": request.path,
        "remote": request.remote,
        "content_type": request.headers.get("Content-Type"),
        "body": redact(body),
    }


async def handle_keenetic(request: web.Request) -> web.Response:
    config: KeeneticConfig = request.app["keenetic_config"]
    raw = await request.text()
    try:
        body: Any = json.loads(raw) if raw else {}
    except ValueError:
        body = {"_raw": raw}
    try:
        await asyncio.to_thread(
            write_record,
            config.log_path,
            _record(request, body),
        )
    except OSError:
        logger.exception("failed to write keenetic probe log")
    return web.json_response(RESPONSE)


def register_keenetic(app: web.Application, config: KeeneticConfig) -> None:
    directory = Path(config.log_path).expanduser().parent
    if not directory.exists():
        logger.warning(
            "keenetic log directory does not exist: %s",
            directory,
        )
    app["keenetic_config"] = config
    app.router.add_post("/keenetic", handle_keenetic)
