from aliceio import F, Router
from aliceio.types import Message, Response

from .common import answer_from_cache

homework_router = Router(name="homework")

HOMEWORK_FILTER = (
    F.command.contains("домашк")
    | F.command.contains("дз")
    | F.command.contains("что задали")
    | F.command.contains("задани")
)


@homework_router.message(HOMEWORK_FILTER)
async def handle_homework(message: Message, cache, worker) -> Response:
    return answer_from_cache(cache, worker)
