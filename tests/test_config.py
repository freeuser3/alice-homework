import json
from pathlib import Path

import pytest

from alice_skill.config import Config, load_config


def _write_config(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "config.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_load_config_valid(tmp_path):
    path = _write_config(tmp_path, {
        "sgo": {"login": "u", "password": "p", "school": "s"},
        "skill_id": "sid",
        "prefetch_interval": 600,
        "host": "0.0.0.0",
        "port": 9000,
    })
    cfg = load_config(path)
    assert isinstance(cfg, Config)
    assert cfg.sgo.login == "u"
    assert cfg.skill_id == "sid"
    assert cfg.prefetch_interval == 600
    assert cfg.host == "0.0.0.0"
    assert cfg.port == 9000


def test_load_config_env_overrides(tmp_path, monkeypatch):
    path = _write_config(tmp_path, {
        "sgo": {"login": "u", "password": "p", "school": "s"},
        "skill_id": "sid",
    })
    monkeypatch.setenv("SGO_LOGIN", "env_user")
    monkeypatch.setenv("SGO_PASSWORD", "env_pass")
    monkeypatch.setenv("SGO_SCHOOL", "env_school")
    monkeypatch.setenv("SKILL_ID", "env_sid")
    cfg = load_config(path)
    assert cfg.sgo.login == "env_user"
    assert cfg.sgo.password == "env_pass"
    assert cfg.sgo.school == "env_school"
    assert cfg.skill_id == "env_sid"


def test_load_config_missing_sgo_raises(tmp_path):
    path = _write_config(tmp_path, {"sgo": {}, "skill_id": "sid"})
    with pytest.raises(ValueError, match="sgo"):
        load_config(path)


def test_load_config_missing_skill_id_raises(tmp_path):
    path = _write_config(tmp_path, {
        "sgo": {"login": "u", "password": "p", "school": "s"},
    })
    with pytest.raises(ValueError, match="skill_id"):
        load_config(path)


def test_load_config_defaults(tmp_path):
    path = _write_config(tmp_path, {
        "sgo": {"login": "u", "password": "p", "school": "s"},
        "skill_id": "sid",
    })
    cfg = load_config(path)
    assert cfg.prefetch_interval == 1800
    assert cfg.host == "127.0.0.1"
    assert cfg.port == 8000
    assert cfg.log_path == "/tmp/alice-homework.log"


def test_load_config_log_path_from_config_and_env(tmp_path, monkeypatch):
    path = _write_config(tmp_path, {
        "sgo": {"login": "u", "password": "p", "school": "s"},
        "skill_id": "sid",
        "log_path": "/var/log/skill.log",
    })
    assert load_config(path).log_path == "/var/log/skill.log"
    monkeypatch.setenv("LOG_PATH", "/tmp/other.log")
    assert load_config(path).log_path == "/tmp/other.log"


def test_load_config_llm_block(tmp_path):
    path = _write_config(tmp_path, {
        "sgo": {"login": "u", "password": "p", "school": "s"},
        "skill_id": "sid",
        "subjects_path": "configs/subjects.json",
        "llm": {"base_url": "https://api.dslab.tech/v1", "api_key": "sk-x",
                "model": "deepseek-v4-flash", "timeout": 30},
    })
    cfg = load_config(path)
    assert cfg.subjects_path == "configs/subjects.json"
    assert cfg.llm is not None
    assert cfg.llm.api_key == "sk-x"
    assert cfg.llm.model == "deepseek-v4-flash"
    assert cfg.llm.timeout == 30


def test_load_config_llm_defaults(tmp_path):
    path = _write_config(tmp_path, {
        "sgo": {"login": "u", "password": "p", "school": "s"},
        "skill_id": "sid",
        "llm": {"api_key": "sk-x"},
    })
    cfg = load_config(path)
    assert cfg.llm is not None
    assert cfg.llm.base_url == "https://api.dslab.tech/v1"
    assert cfg.llm.model == "gpt-4.1-nano"
    assert cfg.llm.timeout == 20.0


def test_load_config_llm_optional(tmp_path):
    path = _write_config(tmp_path, {
        "sgo": {"login": "u", "password": "p", "school": "s"},
        "skill_id": "sid",
    })
    cfg = load_config(path)
    assert cfg.llm is None
    assert cfg.subjects_path == "subjects.json"


def test_load_config_llm_env_overrides(tmp_path, monkeypatch):
    path = _write_config(tmp_path, {
        "sgo": {"login": "u", "password": "p", "school": "s"},
        "skill_id": "sid",
        "llm": {"api_key": "sk-file"},
    })
    monkeypatch.setenv("LLM_API_KEY", "sk-env")
    monkeypatch.setenv("LLM_MODEL", "gpt-4.1-nano")
    monkeypatch.setenv("SUBJECTS_PATH", "/tmp/subj.json")
    cfg = load_config(path)
    assert cfg.llm is not None
    assert cfg.llm.api_key == "sk-env"
    assert cfg.subjects_path == "/tmp/subj.json"


def test_load_config_llm_disabled_when_only_base_url(tmp_path):
    path = _write_config(tmp_path, {
        "sgo": {"login": "u", "password": "p", "school": "s"},
        "skill_id": "sid",
        "llm": {"base_url": "https://api.dslab.tech/v1"},
    })
    cfg = load_config(path)
    assert cfg.llm is None