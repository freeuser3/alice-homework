import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.skillctl import build_screen, clear_screen, render_items


def test_render_items_marks_selected_with_cursor_and_inverse():
    lines = render_items(["Статус", "Старт", "Стоп"], 1)
    assert lines[1] == "> \x1b[7mСтарт\x1b[0m"
    assert lines[0] == "  Статус"
    assert lines[2] == "  Стоп"


def test_render_items_first_selected():
    lines = render_items(["Статус", "Старт"], 0)
    assert lines[0].startswith("> ")
    assert "Статус" in lines[0]


def test_render_items_last_selected():
    lines = render_items(["Статус", "Старт", "Стоп"], 2)
    assert lines[2].startswith("> ")
    assert "Стоп" in lines[2]


def test_clear_screen_uses_ansi():
    assert clear_screen() in ("\x1b[2J\x1b[H", "\x1b[H\x1b[2J")


def test_build_screen_contains_title_footer_and_items():
    labels = ["Статус", "Хвост лога"]
    screen = build_screen(labels, 1, title="Menu", footer="q — выход")
    assert "Menu" in screen
    assert "q — выход" in screen
    assert "Статус" in screen
    assert "Хвост лога" in screen