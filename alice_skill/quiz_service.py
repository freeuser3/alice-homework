"""Ленивая сборка QuizService (quiz-library) из Config навыка."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from quiz_library.llm import LLMClient
from quiz_library.model import LLMConfig
from quiz_library.service import QuizService

from alice_skill.config import Config

logger = logging.getLogger(__name__)


@dataclass
class QuizBundle:
    cfg: Config
    llm: LLMClient
    summary_llm: LLMClient | None = None
    _service: QuizService | None = None
    _names: list[str] = field(default_factory=list)
    _built: bool = False

    def service(self) -> QuizService | None:
        if self._built:
            return self._service
        self._built = True
        try:
            self._service = QuizService.from_config(self.cfg.subjects_path, self.llm)
            with open(self.cfg.subjects_path, encoding="utf-8") as f:
                self._names = list(json.load(f).keys())
        except (OSError, ValueError, KeyError, TypeError) as exc:
            logger.warning("quiz not configured: %s", exc)
            self._service = None
            self._names = []
        return self._service

    @property
    def subject_names(self) -> list[str]:
        self.service()
        return self._names

    async def close(self) -> None:
        await self.llm.close()
        if self.summary_llm is not None:
            await self.summary_llm.close()


def build_quiz(cfg: Config) -> QuizBundle | None:
    if cfg.llm is None or not cfg.llm.api_key:
        return None
    llm = LLMClient(
        LLMConfig(cfg.llm.base_url, cfg.llm.api_key, cfg.llm.model, cfg.llm.timeout)
    )
    summary_llm = None
    if cfg.llm.summary_model:
        summary_llm = LLMClient(
            LLMConfig(cfg.llm.base_url, cfg.llm.api_key, cfg.llm.summary_model, cfg.llm.timeout)
        )
    return QuizBundle(cfg=cfg, llm=llm, summary_llm=summary_llm)