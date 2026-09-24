import json

import pytest

from alice_skill import self_check as sc

DIGEST_JSON = {
    "meta": {"subject": "География", "title": "География. 9 класс", "source_pdf": "GEO.pdf"},
    "paragraphs": {
        "6": {
            "title": "Газовая промышленность",
            "pages": {"start": 22, "end": 25},
            "blocks": [],
        }
    },
}


def write_config(root, *, llm=False):
    cfg = {
        "sgo": {"login": "user", "password": "pass", "school": "Школа"},
        "skill_id": "sid-1",
    }
    if llm:
        cfg["llm"] = {"api_key": "sk-x", "model": "gpt-4.1-nano"}
    (root / "config.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")


def write_subjects(root, digest="digests/geografia.json", patterns=("параграф", "параграфа", "§")):
    data = {
        "География": {
            "book": "География. 9 класс",
            "digest": digest,
            "paragraph_patterns": list(patterns),
        }
    }
    (root / "subjects.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def write_digest(root, digest="digests/geografia.json"):
    path = root / digest
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(DIGEST_JSON, ensure_ascii=False), encoding="utf-8")


def names(checks):
    return [c.name for c in checks]


def hard_failures(checks):
    return [c for c in checks if not c.ok and not c.warn]


def test_missing_config_fails(tmp_path, monkeypatch):
    for var in ("SGO_LOGIN", "SGO_PASSWORD", "SGO_SCHOOL", "SKILL_ID",
                "LLM_API_KEY", "SUBJECTS_PATH"):
        monkeypatch.delenv(var, raising=False)
    checks = sc.run_all(tmp_path)
    assert "config.json" in names(checks)
    assert any(not c.ok for c in checks if c.name == "config.json")
    assert sc.exit_code(checks) == 1


def test_valid_without_llm_warns_but_passes(tmp_path, monkeypatch):
    for var in ("SGO_LOGIN", "SGO_PASSWORD", "SGO_SCHOOL", "SKILL_ID",
                "LLM_API_KEY", "SUBJECTS_PATH"):
        monkeypatch.delenv(var, raising=False)
    write_config(tmp_path, llm=False)
    write_subjects(tmp_path)
    write_digest(tmp_path)
    checks = sc.run_all(tmp_path)
    llm_check = next(c for c in checks if c.name == "llm")
    assert not llm_check.ok
    assert llm_check.warn
    assert sc.exit_code(checks) == 0
    assert not hard_failures(checks)


def test_valid_with_llm_all_ok(tmp_path, monkeypatch):
    for var in ("SGO_LOGIN", "SGO_PASSWORD", "SGO_SCHOOL", "SKILL_ID",
                "LLM_API_KEY", "SUBJECTS_PATH"):
        monkeypatch.delenv(var, raising=False)
    write_config(tmp_path, llm=True)
    write_subjects(tmp_path)
    write_digest(tmp_path)
    checks = sc.run_all(tmp_path)
    assert all(c.ok for c in checks) or all(c.ok or c.warn for c in checks)
    assert sc.exit_code(checks) == 0


def test_missing_subjects_fails(tmp_path, monkeypatch):
    for var in ("SGO_LOGIN", "SGO_PASSWORD", "SGO_SCHOOL", "SKILL_ID",
                "LLM_API_KEY", "SUBJECTS_PATH"):
        monkeypatch.delenv(var, raising=False)
    write_config(tmp_path, llm=True)
    checks = sc.run_all(tmp_path)
    assert "subjects.json" in names(checks)
    assert any(not c.ok for c in checks if c.name == "subjects.json")
    assert sc.exit_code(checks) == 1


def test_invalid_subjects_json_fails(tmp_path, monkeypatch):
    for var in ("SGO_LOGIN", "SGO_PASSWORD", "SGO_SCHOOL", "SKILL_ID",
                "LLM_API_KEY", "SUBJECTS_PATH"):
        monkeypatch.delenv(var, raising=False)
    write_config(tmp_path, llm=True)
    (tmp_path / "subjects.json").write_text("{not json", encoding="utf-8")
    checks = sc.run_all(tmp_path)
    assert any(not c.ok for c in checks if c.name == "subjects.json")
    assert sc.exit_code(checks) == 1


def test_subjects_without_entries_fails(tmp_path, monkeypatch):
    for var in ("SGO_LOGIN", "SGO_PASSWORD", "SGO_SCHOOL", "SKILL_ID",
                "LLM_API_KEY", "SUBJECTS_PATH"):
        monkeypatch.delenv(var, raising=False)
    write_config(tmp_path, llm=True)
    (tmp_path / "subjects.json").write_text("{}", encoding="utf-8")
    checks = sc.run_all(tmp_path)
    assert any(not c.ok for c in checks if c.name == "subjects.json")
    assert sc.exit_code(checks) == 1


def test_missing_digest_file_fails(tmp_path, monkeypatch):
    for var in ("SGO_LOGIN", "SGO_PASSWORD", "SGO_SCHOOL", "SKILL_ID",
                "LLM_API_KEY", "SUBJECTS_PATH"):
        monkeypatch.delenv(var, raising=False)
    write_config(tmp_path, llm=True)
    write_subjects(tmp_path)  # digest отсутствует
    checks = sc.run_all(tmp_path)
    digest_fails = [c for c in checks if c.name.startswith("digest") and not c.ok]
    assert digest_fails
    assert sc.exit_code(checks) == 1


def test_broken_digest_json_fails(tmp_path, monkeypatch):
    for var in ("SGO_LOGIN", "SGO_PASSWORD", "SGO_SCHOOL", "SKILL_ID",
                "LLM_API_KEY", "SUBJECTS_PATH"):
        monkeypatch.delenv(var, raising=False)
    write_config(tmp_path, llm=True)
    write_subjects(tmp_path)
    path = tmp_path / "digests" / "geografia.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{broken", encoding="utf-8")
    checks = sc.run_all(tmp_path)
    assert any(c.name.startswith("digest") and not c.ok for c in checks)
    assert sc.exit_code(checks) == 1


def test_empty_digest_paragraphs_fails(tmp_path, monkeypatch):
    for var in ("SGO_LOGIN", "SGO_PASSWORD", "SGO_SCHOOL", "SKILL_ID",
                "LLM_API_KEY", "SUBJECTS_PATH"):
        monkeypatch.delenv(var, raising=False)
    write_config(tmp_path, llm=True)
    write_subjects(tmp_path)
    path = tmp_path / "digests" / "geografia.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"meta": {}, "paragraphs": {}}), encoding="utf-8")
    checks = sc.run_all(tmp_path)
    assert any(c.name.startswith("digest") and not c.ok for c in checks)
    assert sc.exit_code(checks) == 1


def test_paragraph_missing_required_fields_fails(tmp_path, monkeypatch):
    for var in ("SGO_LOGIN", "SGO_PASSWORD", "SGO_SCHOOL", "SKILL_ID",
                "LLM_API_KEY", "SUBJECTS_PATH"):
        monkeypatch.delenv(var, raising=False)
    write_config(tmp_path, llm=True)
    write_subjects(tmp_path)
    path = tmp_path / "digests" / "geografia.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    bad = {"meta": {}, "paragraphs": {"6": {"title": "", "pages": {}}}}
    path.write_text(json.dumps(bad), encoding="utf-8")
    checks = sc.run_all(tmp_path)
    assert any(c.name.startswith("digest") and not c.ok for c in checks)
    assert sc.exit_code(checks) == 1


def test_parse_check_ok(tmp_path, monkeypatch):
    for var in ("SGO_LOGIN", "SGO_PASSWORD", "SGO_SCHOOL", "SKILL_ID",
                "LLM_API_KEY", "SUBJECTS_PATH"):
        monkeypatch.delenv(var, raising=False)
    write_config(tmp_path, llm=True)
    write_subjects(tmp_path)
    write_digest(tmp_path)
    checks = sc.run_all(tmp_path)
    assert any(c.name == "parse" and c.ok for c in checks)


def test_parse_check_uses_subjects_patterns(tmp_path, monkeypatch):
    for var in ("SGO_LOGIN", "SGO_PASSWORD", "SGO_SCHOOL", "SKILL_ID",
                "LLM_API_KEY", "SUBJECTS_PATH"):
        monkeypatch.delenv(var, raising=False)
    write_config(tmp_path, llm=True)
    # только «параграф» — строка «прочитать параграф 6» должна распознаться
    write_subjects(tmp_path, patterns=("параграф",))
    write_digest(tmp_path)
    checks = sc.run_all(tmp_path)
    assert any(c.name == "parse" and c.ok for c in checks)


def test_quiz_library_import_ok():
    assert sc.check_quiz_library().ok


def test_exit_code_consideres_warn():
    warning = sc.Check(name="llm", ok=False, warn=True, detail="off")
    ok = sc.Check(name="config", ok=True, detail="ok")
    fail = sc.Check(name="digest", ok=False, detail="missing")
    assert sc.exit_code([ok, warning]) == 0
    assert sc.exit_code([ok, fail]) == 1
    assert sc.exit_code([ok, fail, warning]) == 1


def test_check_formatting_is_utf8_safe():
    fail = sc.Check(name="config", ok=False, detail="нет файла")
    assert isinstance(fail.line(), str)
    assert "config" in fail.line()