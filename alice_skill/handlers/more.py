from aliceio import F, Router
from aliceio.types import Message, Response

from alice_skill.quiz_state import QuizSlot

from .common import HINT_TEXT
from .quiz import PREMATURE_MORE_TEXT, QUIZ_FAIL_TEXT

more_router = Router(name="more")


@more_router.message(F.command == "дальше")
async def handle_more(message: Message, cache, slot: QuizSlot | None = None) -> Response:
    if slot is not None:
        if slot.question is not None:
            text = slot.question
            slot.clear()
            return Response(text=text)
        if slot.task is not None:
            if slot.task.done():
                slot.clear()
                return Response(text=QUIZ_FAIL_TEXT)
            return Response(text=PREMATURE_MORE_TEXT)
    result = cache.get()
    if result is not None:
        return Response(text=result.text)
    return Response(text=HINT_TEXT)
