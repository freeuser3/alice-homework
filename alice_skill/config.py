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
class LlmConfig:
    base_url: str = "https://api.dslab.tech/v1"
    api_key: str = ""
    model: str = "gpt-4.1-nano"
    summary_model: str = "gpt-4.1-nano"
    timeout: float = 20.0


@dataclass(frozen=True)
class Config:
    sgo: SgoConfig
    skill_id: str
    prefetch_interval: int = 1800
    host: str = "127.0.0.1"
    port: int = 8000
    subjects_path: str = "subjects.json"
    log_path: str = "/tmp/alice-homework.log"
    llm: LlmConfig | None = None
    memory_path: str = "memory.json"
    memory_max_weeks: int = 8


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
    subjects_path = os.environ.get("SUBJECTS_PATH") or raw.get("subjects_path", "subjects.json")
    log_path = os.environ.get("LOG_PATH") or raw.get("log_path", "/tmp/alice-homework.log")

    llm_raw: dict = raw.get("llm", {}) or {}
    api_key = os.environ.get("LLM_API_KEY") or llm_raw.get("api_key", "")
    llm = None
    if api_key:
        llm = LlmConfig(
            base_url=os.environ.get("LLM_BASE_URL")
            or llm_raw.get("base_url", "https://api.dslab.tech/v1"),
            api_key=api_key,
            model=os.environ.get("LLM_MODEL") or llm_raw.get("model", "gpt-4.1-nano"),
            summary_model=os.environ.get("LLM_SUMMARY_MODEL")
            or llm_raw.get("summary_model", "gpt-4.1-nano"),
            timeout=float(os.environ.get("LLM_TIMEOUT") or llm_raw.get("timeout", 20.0)),
        )

    return Config(
        sgo=sgo, skill_id=skill_id, prefetch_interval=prefetch,
        host=host, port=port, subjects_path=subjects_path,
        log_path=log_path, llm=llm,
        memory_path=os.environ.get("MEMORY_PATH") or raw.get("memory_path", "memory.json"),
        memory_max_weeks=int(os.environ.get("MEMORY_MAX_WEEKS") or raw.get("memory_max_weeks", 8)),
    )