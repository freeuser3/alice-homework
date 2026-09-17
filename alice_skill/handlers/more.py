from aliceio import F, Router
from aliceio.types import Message, Response

from .common import HINT_TEXT

more_router = Router(name="more")


@more_router.message(F.command == "дальше")
async def handle_more(message: Message, cache) -> Response:
    result = cache.get()
    if result is not None:
        return Response(text=result.text)
    return Response(text=HINT_TEXT)
