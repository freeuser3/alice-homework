from aliceio import F, Router
from aliceio.types import Message, Response

help_router = Router(name="help")

HELP_FILTER = (
    F.command.contains("помощ")
    | F.command.contains("справк")
    | F.command.contains("что ты умеешь")
    | F.command.contains("возможност")
    | F.command.contains("помоги")
)

HELP_TEXT = (
    "Я помогаю с учёбой. "
    "Домашка — скажи «что задали» или «домашка». "
    "Уроки — скажи «какие завтра уроки» или «расписание». "
    "Викторина — скажи «спроси по географии» или «проверь меня». "
    "Подробнее про задание — «дальше»."
)


@help_router.message(HELP_FILTER)
async def handle_help(message: Message) -> Response:
    return Response(text=HELP_TEXT)