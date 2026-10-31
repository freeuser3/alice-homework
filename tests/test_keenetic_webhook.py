import hashlib
import json

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from keenetic_skill.config import KeeneticConfig
from keenetic_skill.webhook import register_keenetic


def _make_app(tmp_path):
    app = web.Application()
    config = KeeneticConfig(
        skill_id="test-keenetic",
        log_path=str(tmp_path / "keenetic.log"),
    )
    register_keenetic(app, config)
    return app, tmp_path / "keenetic.log"


@pytest.mark.asyncio
async def test_keenetic_endpoint_logs_and_responds(tmp_path):
    app, log_path = _make_app(tmp_path)
    async with TestClient(TestServer(app)) as client:
        resp = await client.post(
            "/keenetic",
            json={
                "session": {
                    "user": {
                        "user_id": "u1",
                        "access_token": "secret",
                    },
                },
                "request": {"command": "привет"},
            },
        )
        assert resp.status == 200
        assert await resp.json() == {
            "response": {"text": "Записано", "end_session": False},
            "version": "1.0",
        }
    records = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(records) == 1
    assert records[0]["body"]["session"]["user"]["user_id"] == "u1"
    assert records[0]["body"]["session"]["user"]["access_token"] == "***"
    assert records[0]["body"]["request"]["command"] == "привет"


@pytest.mark.asyncio
async def test_keenetic_invalid_json_logs_metadata_only(tmp_path):
    app, log_path = _make_app(tmp_path)
    payload = b'{"access_token": "secret"'
    async with TestClient(TestServer(app)) as client:
        resp = await client.post(
            "/keenetic",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 200
    text = log_path.read_text(encoding="utf-8")
    assert "secret" not in text
    record = json.loads(text.splitlines()[0])
    assert "_raw" not in record["body"]
    assert record["body"]["_raw_len"] == len(payload)
    assert record["body"]["raw_sha256"] == hashlib.sha256(payload).hexdigest()


@pytest.mark.asyncio
async def test_keenetic_invalid_utf8_body_is_accepted(tmp_path):
    app, log_path = _make_app(tmp_path)
    async with TestClient(TestServer(app)) as client:
        resp = await client.post(
            "/keenetic",
            data=b"\xff\xfe",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 200
    record = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
    assert record["body"]["_raw_len"] == 2
    assert "raw_sha256" in record["body"]


@pytest.mark.asyncio
async def test_keenetic_get_is_not_allowed(tmp_path):
    app, _ = _make_app(tmp_path)
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/keenetic")
        assert resp.status == 405
