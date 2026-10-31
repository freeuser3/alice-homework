from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KeeneticConfig:
    skill_id: str
    log_path: str = "keenetic.log"


def load_keenetic_config(raw: dict | None) -> KeeneticConfig | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("keenetic must be an object")
    skill_id = str(raw.get("skill_id") or "").strip()
    if not skill_id:
        raise ValueError("keenetic.skill_id must be set")
    log_path = str(raw.get("log_path") or "keenetic.log")
    return KeeneticConfig(skill_id=skill_id, log_path=log_path)
