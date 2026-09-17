from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SgoConfig:
    login: str
    password: str
    school: str


@dataclass(frozen=True)
class Config:
    sgo: SgoConfig
    skill_id: str
    prefetch_interval: int = 1800
    host: str = "127.0.0.1"
    port: int = 8000


def load_config(path: str | Path = "config.json") -> Config:
    with open(path, encoding="utf-8") as f:
        raw: dict = json.load(f)

    sgo_raw: dict = raw.get("sgo", {})
    sgo = SgoConfig(
        login=os.environ.get("SGO_LOGIN") or sgo_raw.get("login", ""),
        password=os.environ.get("SGO_PASSWORD") or sgo_raw.get("password", ""),
        school=os.environ.get("SGO_SCHOOL") or sgo_raw.get("school", ""),
    )
    if not (sgo.login and sgo.password and sgo.school):
        raise ValueError(
            "sgo.login, sgo.password, sgo.school must be set in config.json "
            "or via SGO_LOGIN / SGO_PASSWORD / SGO_SCHOOL env vars"
        )

    skill_id = os.environ.get("SKILL_ID") or raw.get("skill_id", "")
    if not skill_id:
        raise ValueError("skill_id must be set in config.json or SKILL_ID env var")

    prefetch = int(os.environ.get("PREFETCH_INTERVAL") or raw.get("prefetch_interval", 1800))
    host = raw.get("host", "127.0.0.1")
    port = int(raw.get("port", 8000))

    return Config(sgo=sgo, skill_id=skill_id, prefetch_interval=prefetch, host=host, port=port)