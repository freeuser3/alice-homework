from aliceio import F, Router
from aliceio.types import Message, Response

from .common import answer_from_cache

start_router = Router(name="start")


@start_router.message(F.session.new)
async def handle_start(message: Message, cache, worker) -> Response:
    return answer_from_cache(cache, worker)
