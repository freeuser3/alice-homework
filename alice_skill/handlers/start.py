from aliceio import F, Router
from aliceio.types import Message, Response

from .common import GREETING_TEXT

start_router = Router(name="start")


@start_router.message(F.session.new)
async def handle_start(message: Message, cache, worker) -> Response:
    return Response(text=GREETING_TEXT)
