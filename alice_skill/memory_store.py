"""Память наставника: итоги недель + сжатый дайджест в JSON-файле."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_MAX_WEEKS = 8


@dataclass
class SummaryMemory:
    """Хранит последние итоги недель и сжатый дайджест прошлых недель.

    Запись каждой недели: {"week": iso, "facts": dict, "summary": str}.
    При накоплении max_weeks записей лишние недели сворачиваются в digest
    (асинхронно, через LLM), в файле остаются последние две сырые недели.
    """

    path: str | Path
    max_weeks: int = DEFAULT_MAX_WEEKS
    weeks: list[dict] = field(default_factory=list)
    digest: str = ""

    def load(self) -> None:
        self.weeks = []
        self.digest = ""
        try:
            with open(self.path, encoding="utf-8") as f:
                raw = json.load(f)
            self.weeks = raw.get("weeks", [])
            self.digest = raw.get("digest", "")
        except (OSError, ValueError):
            self.weeks = []
            self.digest = ""

    def save(self) -> None:
        data = {"weeks": self.weeks, "digest": self.digest}
        tmp = Path(self.path).with_name(Path(self.path).name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp.replace(self.path)

    def append(self, week: str, facts: dict, summary: str) -> None:
        self.weeks.append({"week": week, "facts": facts, "summary": summary})

    def overflow(self) -> list[dict]:
        """Недели, которые пора свернуть в дайджест (все, кроме последних двух)."""
        if len(self.weeks) <= 2:
            return []
        return list(self.weeks[:-2])

    def needs_digest(self) -> bool:
        return len(self.weeks) >= self.max_weeks

    def fold_into_digest(self, digest: str) -> None:
        """Сворачивает все недели кроме последних двух в digest."""
        if not self.weeks:
            return
        combined = "\n".join(
            [self.digest, digest] if self.digest else [digest]
        ).strip()
        self.digest = combined
        recent = list(self.weeks[-2:])
        self.weeks = recent

    def prune(self) -> None:
        """Просто обрезает недели до max_weeks (без сворачивания в дайджест)."""
        if len(self.weeks) > self.max_weeks:
            self.weeks = list(self.weeks[-self.max_weeks:])

    def render_overflow_text(self, entries: list[dict]) -> str:
        """Недели для дайджеста в виде текста."""
        lines = []
        if self.digest:
            lines.append("Прежний дайджест: " + self.digest)
        for e in entries:
            lines.append(
                f"Неделя {e['week']}: {render_facts_line(e['facts'])}. Итог: {e['summary']}"
            )
        return "\n".join(lines)

    def render_memory_block(self) -> str:
        """Блок «память о прошлых неделях» для контекста LLM."""
        lines: list[str] = []
        if self.digest:
            lines.append(f"Дайджест прошлых недель: {self.digest}")
        for entry in self.weeks[-2:]:
            lines.append(f"Прошлая неделя {entry['week']}: «{entry['summary']}»")
        return "\n".join(lines)


def render_facts_line(facts: dict) -> str:
    """Сжатые факты недели одной строкой."""
    parts: list[str] = []
    if facts.get("avg") is not None:
        parts.append(f"средний балл {facts['avg']}")
    if facts.get("marks_count"):
        parts.append(f"оценок: {facts['marks_count']}")
    if facts.get("strong"):
        parts.append("сильные: " + ", ".join(facts["strong"]))
    if facts.get("weak"):
        parts.append("слабые: " + ", ".join(facts["weak"]))
    if facts.get("overdue"):
        parts.append(f"долгов: {facts['overdue']}")
    return "; ".join(parts)