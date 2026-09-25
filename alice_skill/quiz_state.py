"""Отложенное состояние викторины: слот «подумать-и-ответь-по-дальше»."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass


@dataclass
class QuizSlot:
    subject: str | None = None
    paragraph: str | None = None
    question: str | None = None
    task: asyncio.Task | None = None

    def set_pending(self, subject: str, paragraph: str | None, task: asyncio.Task) -> None:
        self.subject = subject
        self.paragraph = paragraph
        self.task = task
        self.question = None

    def finish(self, subject: str, question: str | None) -> None:
        if self.task is not None and self.task is asyncio.current_task():
            self.subject = subject
            self.question = question

    def clear(self) -> None:
        self.subject = None
        self.paragraph = None
        self.question = None
        self.task = None

    @property
    def has_pending(self) -> bool:
        return self.task is not None or self.question is not None


@dataclass
class SummarySlot:
    """Отложенный текст итога недели: слот «подумать-и-ответь-по-дальше»."""

    text: str | None = None
    task: asyncio.Task | None = None

    def set_pending(self, task: asyncio.Task) -> None:
        self.task = task
        self.text = None

    def finish(self, text: str | None) -> None:
        if self.task is not None and self.task is asyncio.current_task():
            self.text = text

    def clear(self) -> None:
        self.text = None
        self.task = None

    @property
    def has_pending(self) -> bool:
        return self.task is not None or self.text is not None