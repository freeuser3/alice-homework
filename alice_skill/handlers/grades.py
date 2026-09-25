from aliceio import F, Router
from aliceio.types import Message, Response

from alice_skill.homework import format_marks

from .common import PREMATURE_TEXT

grades_router = Router(name="grades")

GRADES_FILTER = (
    F.command.contains("двоек")
    | F.command.contains("двойк")
    | F.command.contains("троек")
    | F.command.contains("тройк")
    | F.command.contains("четвёрок")
    | F.command.contains("четвёрк")
    | F.command.contains("четверок")
    | F.command.contains("четверк")
    | F.command.contains("пятёрок")
    | F.command.contains("пятёрк")
    | F.command.contains("пятерок")
    | F.command.contains("пятерк")
)

_GRADE_MARK_WORDS: dict[str, int] = {
    "двоек": 2,
    "двойк": 2,
    "троек": 3,
    "тройк": 3,
    "четвёрок": 4,
    "четвёрк": 4,
    "четверок": 4,
    "четверк": 4,
    "пятёрок": 5,
    "пятёрк": 5,
    "пятерок": 5,
    "пятерк": 5,
}


def detect_grade(command: str) -> int | None:
    low = command.lower()
    for word, mark in _GRADE_MARK_WORDS.items():
        if word in low:
            return mark
    return None


@grades_router.message(GRADES_FILTER)
async def handle_grades(message: Message, cache, worker) -> Response:
    result = cache.get()
    if result is not None and result.status in ("ok", "empty"):
        mark = detect_grade(message.command)
        counts = result.marks.get(mark, {}) if mark is not None else {}
        return Response(text=format_marks(mark, counts))
    worker.refresh_now()
    return Response(text=PREMATURE_TEXT)