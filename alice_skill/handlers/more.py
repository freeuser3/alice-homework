from aliceio import F, Router
from aliceio.types import Message, Response

from alice_skill.quiz_state import QuizSlot, SummarySlot

from .common import HINT_TEXT
from .quiz import PREMATURE_MORE_TEXT, QUIZ_FAIL_TEXT
from .summary import PREMATURE_SUMMARY_MORE_TEXT, SUMMARY_FAIL_TEXT

more_router = Router(name="more")


@more_router.message(F.command == "дальше")
async def handle_more(
    message: Message, cache, slot: QuizSlot | None = None,
    summary_slot: SummarySlot | None = None,
) -> Response:
    if summary_slot is not None:
        if summary_slot.text is not None:
            text = summary_slot.text
            summary_slot.clear()
            return Response(text=text)
        if summary_slot.task is not None:
            if summary_slot.task.done():
                summary_slot.clear()
                return Response(text=SUMMARY_FAIL_TEXT)
            return Response(text=PREMATURE_SUMMARY_MORE_TEXT)
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
