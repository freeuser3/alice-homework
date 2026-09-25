from __future__ import annotations

from aliceio.types import Response

from alice_skill.cache import HomeworkCache
from alice_skill.worker import PrefetchWorker

PREMATURE_TEXT = "Секунду, заглядываю в дневник. Скажи «дальше»."
HINT_TEXT = "Я умею рассказывать домашку. Скажи «что задали»."
TIMEOUT_TEXT = "Не успела посмотреть в дневник. Скажи «что задали» ещё раз."
ERROR_TEXT = "Что-то пошло не так. Попробуй, пожалуйста, ещё раз."


def answer_from_cache(
    cache: HomeworkCache, worker: PrefetchWorker, field: str = "text",
) -> Response:
    result = cache.get()
    if result is not None and result.status in ("ok", "empty"):
        return Response(text=getattr(result, field))
    worker.refresh_now()
    return Response(text=PREMATURE_TEXT)
