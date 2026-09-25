from aliceio import F, Router
from aliceio.types import Message, Response

from .common import PREMATURE_TEXT

timetable_router = Router(name="timetable")

TIMETABLE_FILTER = (
    F.command.contains("урок")
    | F.command.contains("расписани")
    | F.command.contains("что завтра")
)
NO_LESSONS_TEXT = "Уроков на завтра нет."


@timetable_router.message(TIMETABLE_FILTER)
async def handle_timetable(message: Message, cache, worker) -> Response:
    result = cache.get()
    if result is not None and result.status in ("ok", "empty"):
        text = result.lessons_text or NO_LESSONS_TEXT
        return Response(text=text)
    worker.refresh_now()
    return Response(text=PREMATURE_TEXT)