from __future__ import annotations

import random

from aliceio.types import Response

from alice_skill.cache import HomeworkCache
from alice_skill.worker import PrefetchWorker

PREMATURE_TEXT = "Секунду, заглядываю в дневник. Скажи «дальше»."
HINT_TEXT = "Я умею рассказывать домашку. Скажи «что задали»."
TIMEOUT_TEXT = "Не успела посмотреть в дневник. Скажи «что задали» ещё раз."
ERROR_TEXT = "Что-то пошло не так. Попробуй, пожалуйста, ещё раз."
GREETING_PREFIX = "Привет! Я помогаю с учёбой."
GREETING_EXAMPLES = [
    "«что задали»",
    "«какие завтра уроки»",
    "«сколько пятёрок»",
    "«итоги за неделю»",
    "«спроси по географии»",
]


def build_greeting(rng: random.Random | None = None) -> str:
    rng = rng or random.Random()
    example = rng.choice(GREETING_EXAMPLES)
    return f"{GREETING_PREFIX} Скажи, например, {example}."


def answer_from_cache(
    cache: HomeworkCache, worker: PrefetchWorker, field: str = "text",
) -> Response:
    result = cache.get()
    if result is not None and result.status in ("ok", "empty"):
        return Response(text=getattr(result, field))
    worker.refresh_now()
    return Response(text=PREMATURE_TEXT)
