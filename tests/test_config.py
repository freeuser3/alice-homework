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