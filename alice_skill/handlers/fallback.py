from aliceio import Router
from aliceio.types import Message, Response

from .common import HINT_TEXT

fallback_router = Router(name="fallback")


@fallback_router.message()
async def handle_fallback(message: Message) -> Response:
    return Response(text=HINT_TEXT)
