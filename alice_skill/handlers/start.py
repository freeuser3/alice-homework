import random

from aliceio import F, Router
from aliceio.types import Message, Response

from .common import build_greeting

start_router = Router(name="start")


@start_router.message(F.session.new)
async def handle_start(
    message: Message, cache, worker, rng: random.Random | None = None,
) -> Response:
    return Response(text=build_greeting(rng))
