"""Самопроверка развёрнутого навыка: конфиг, предметы, выжимки, викторина."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from quiz_library.parser import parse_paragraph

from alice_skill.config import Config, load_config

_SAMPLE = "пересказать параграф 6"


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str = ""
    warn: bool = False

    def line(self) -> str:
        mark = "OK  " if self.ok else ("WARN" if self.warn else "FAIL")
        return f"[{mark}] {self.name}: {self.detail}"


def check_config(root: Path) -> tuple[Config | None, Check]:
    path = root / "config.json"
    if not path.is_file():
        return None, Check("config.json", False, "файл не найден")
    try:
        cfg = load_config(path)
    except (OSError, ValueError) as exc:
        return None, Check("config.json", False, str(exc))
    return cfg, Check("config.json", True, "sgo и skill_id заполнены")


def check_llm(cfg: Config) -> Check:
    if cfg.llm is None or not cfg.llm.api_key:
        return Check("llm", False, "llm.api_key пуст — викторина выключена", warn=True)
    return Check("llm", True, f"викторина включена ({cfg.llm.model})")


def _digest_checks(name: str, raw: dict, root: Path) -> list[Check]:
    digest = raw.get("digest", "")
    path = Path(digest)
    if not path.is_absolute():
        path = root / path
    if not path.is_file():
        return [Check(f"digest:{name}", False, f"файл не найден: {path}")]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [Check(f"digest:{name}", False, f"не читается JSON: {exc}")]
    paragraphs = data.get("paragraphs", {})
    if not paragraphs:
        return [Check(f"digest:{name}", False, "paragraphs пуст")]
    for num, para in paragraphs.items():
        pages = para.get("pages", {})
        ok = (
            isinstance(num, str)
            and isinstance(para.get("title"), str)
            and bool(para["title"])
            and isinstance(pages.get("start"), int)
            and isinstance(pages.get("end"), int)
        )
        if not ok:
            return [Check(f"digest:{name}", False, f"параграф {num}: пустой title или pages")]
    return [Check(f"digest:{name}", True, f"{len(paragraphs)} параграф(ов)")]


def check_subjects(cfg: Config, root: Path) -> list[Check]:
    subj = Path(cfg.subjects_path)
    if not subj.is_absolute():
        subj = root / subj
    if not subj.is_file():
        return [Check("subjects.json", False, f"файл не найден: {subj}")]
    try:
        raw = json.loads(subj.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [Check("subjects.json", False, f"не читается JSON: {exc}")]
    if not raw:
        return [Check("subjects.json", False, "список предметов пуст")]
    checks = [Check("subjects.json", True, f"{len(raw)} предмет(ов)")]
    for name, entry in raw.items():
        checks.extend(_digest_checks(name, entry, root))
    return checks


def check_parse(raw: dict) -> Check:
    missed = []
    for name, entry in raw.items():
        patterns = entry.get("paragraph_patterns", [])
        if not patterns:
            missed.append(f"{name}: нет паттернов")
            continue
        number = parse_paragraph(_SAMPLE, patterns)
        if number != 6:
            missed.append(f"{name}: «{_SAMPLE}» = {number}")
    if missed:
        return Check("parse", False, "; ".join(missed))
    return Check("parse", True, f"«{_SAMPLE}» = параграф 6 по всем предметам")


def check_quiz_library() -> Check:
    try:
        import quiz_library  # noqa: F401
    except ImportError:
        return Check("quiz-library", False, "не установлена")
    return Check("quiz-library", True, "импорт ok")


def run_all(root: str | Path = ".") -> list[Check]:
    root = Path(root)
    cfg, config_check = check_config(root)
    checks = [config_check]
    if cfg is None:
        return checks
    checks.append(check_llm(cfg))
    checks.extend(check_subjects(cfg, root))
    checks.append(check_parse(_load_raw_subjects(cfg, root)))
    checks.append(check_quiz_library())
    return checks


def _load_raw_subjects(cfg: Config, root: Path) -> dict:
    subj = Path(cfg.subjects_path)
    if not subj.is_absolute():
        subj = root / subj
    try:
        return json.loads(subj.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def exit_code(checks: list[Check]) -> int:
    return 1 if any(not c.ok and not c.warn for c in checks) else 0


def main(argv: list[str] | None = None) -> int:
    root = Path(argv[0]) if argv else Path(".")
    checks = run_all(root)
    for c in checks:
        print(c.line())
    code = exit_code(checks)
    print("все проверки пройдены" if code == 0 else "есть проблемы")
    return code


if __name__ == "__main__":
    import sys

    sys.exit(main(sys.argv[1:]))