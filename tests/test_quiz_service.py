import json

import pytest

from alice_skill.config import Config, LlmConfig, SgoConfig
from alice_skill.quiz_service import QuizBundle, build_quiz


def _cfg(tmp_path, *, api_key="sk-x", subjects="subjects.json") -> Config:
    return Config(
        sgo=SgoConfig(login="u", password="p", school="s"),
        skill_id="sid",
        subjects_path=str(tmp_path / subjects),
        llm=LlmConfig(api_key=api_key),
    )


def test_build_quiz_none_without_llm(tmp_path):
    cfg = Config(sgo=SgoConfig(login="u", password="p", school="s"), skill_id="sid")
    assert build_quiz(cfg) is None


def test_build_quiz_none_without_api_key(tmp_path):
    assert build_quiz(_cfg(tmp_path, api_key="")) is None


def test_build_quiz_returns_bundle(tmp_path):
    bundle = build_quiz(_cfg(tmp_path))
    assert bundle is not None
    assert bundle.service() is None  # subjects.json ещё нет


def test_service_and_subject_names(tmp_path):
    subjects_path = tmp_path / "subjects.json"
    subjects_path.write_text(
        json.dumps({"География": {"digest": "digests/geografia.json",
                                  "paragraph_patterns": ["параграф", "§"]}}),
        encoding="utf-8",
    )
    bundle = build_quiz(_cfg(tmp_path, subjects=subjects_path.name))
    assert bundle is not None
    svc = bundle.service()
    assert svc is not None
    assert bundle.subject_names == ["География"]
    assert bundle.service() is svc  # лениво, один раз


def test_broken_subjects_json_yields_none(tmp_path):
    bad = tmp_path / "subjects.json"
    bad.write_text("{not json", encoding="utf-8")
    bundle = build_quiz(_cfg(tmp_path, subjects=bad.name))
    assert bundle is not None
    assert bundle.service() is None
    assert bundle.subject_names == []


@pytest.mark.asyncio
async def test_close_awaits_llm_close(tmp_path):
    bundle = build_quiz(_cfg(tmp_path))
    assert bundle is not None
    await bundle.close()  # не падает; session не создавалась


def test_build_quiz_creates_separate_summary_llm(tmp_path):
    cfg = _cfg(tmp_path)
    cfg = Config(
        sgo=cfg.sgo, skill_id=cfg.skill_id, subjects_path=cfg.subjects_path,
        llm=LlmConfig(api_key="sk-x", model="gpt-4.1-nano",
                      summary_model="gpt-5.4-nano"),
    )
    bundle = build_quiz(cfg)
    assert bundle is not None
    assert bundle.summary_llm is not None
    assert bundle.summary_llm is not bundle.llm
    assert bundle.summary_llm.config.model == "gpt-5.4-nano"
    assert bundle.llm.config.model == "gpt-4.1-nano"


def test_build_quiz_default_summary_model_same_as_main(tmp_path):
    bundle = build_quiz(_cfg(tmp_path))
    assert bundle is not None
    assert bundle.summary_llm is not None
    assert bundle.summary_llm.config.model == "gpt-4.1-nano"
    assert bundle.llm.config.model == "gpt-4.1-nano"


def test_build_quiz_no_summary_llm_when_empty_model(tmp_path):
    cfg = _cfg(tmp_path)
    cfg = Config(
        sgo=cfg.sgo, skill_id=cfg.skill_id, subjects_path=cfg.subjects_path,
        llm=LlmConfig(api_key="sk-x", summary_model=""),
    )
    bundle = build_quiz(cfg)
    assert bundle is not None
    assert bundle.summary_llm is None


def test_summary_llm_model_from_cfg(tmp_path):
    cfg = _cfg(tmp_path)
    cfg = Config(
        sgo=cfg.sgo, skill_id=cfg.skill_id, subjects_path=cfg.subjects_path,
        llm=LlmConfig(api_key="sk-x", model="gpt-4.1-nano",
                      summary_model="deepseek-v4-flash"),
    )
    bundle = build_quiz(cfg)
    assert bundle is not None
    assert bundle.summary_llm is not None
    assert bundle.summary_llm.config.model == "deepseek-v4-flash"

    # фоновая модель (quiz) остаётся прежней
    assert bundle.llm.config.model == "gpt-4.1-nano"