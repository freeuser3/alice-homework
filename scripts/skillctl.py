"""Интерактивная панель управления навыком: python scripts/skillctl.py."""
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = Path("/tmp/alice-homework.log")
QUIZLIB_SRC = "git+https://github.com/freeuser3/quiz-library.git"
PROC_MODULE = "alice_skill.skill"
PROC_PATTERN = PROC_MODULE


def clear_screen() -> str:
    return "\x1b[2J\x1b[H"


def inverse(text: str) -> str:
    return f"\x1b[7m{text}\x1b[0m"


def render_items(labels: list[str], selected: int) -> list[str]:
    lines = []
    for i, label in enumerate(labels):
        marker = ">" if i == selected else " "
        text = inverse(label) if i == selected else label
        lines.append(f"{marker} {text}")
    return lines


def build_screen(labels: list[str], selected: int, title: str, footer: str) -> str:
    parts = [clear_screen(), title, ""]
    parts.extend(render_items(labels, selected))
    parts.extend(["", footer, ""])
    return "\n".join(parts)


def get_key() -> str:
    if os.name == "nt":
        import msvcrt

        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"):
            ch = msvcrt.getwch()
            return {"H": "up", "P": "down"}.get(ch, ch)
        return {"\r": "enter", "\n": "enter", "q": "q", "Q": "q"}.get(ch, ch)

    import termios

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    new = termios.tcgetattr(fd)
    new[3] &= ~(termios.ICANON | termios.ECHO)
    new[6][termios.VMIN] = 1
    new[6][termios.VTIME] = 0
    try:
        termios.tcsetattr(fd, termios.TCSADRAIN, new)
        data = os.read(fd, 1)
        if data == b"\x1b":
            seq = os.read(fd, 2)
            return {"[A": "up", "[B": "down"}.get(seq.decode(errors="replace"), "")
        char = data.decode(errors="replace")
        return {"\r": "enter", "\n": "enter", "q": "q", "Q": "q"}.get(char, "")
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def run(args, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=ROOT, **kw)


def pgrep() -> str:
    try:
        proc = run(["pgrep", "-f", PROC_PATTERN], capture_output=True, text=True)
        return proc.stdout.strip()
    except FileNotFoundError:
        return ""


def is_running() -> bool:
    return bool(pgrep())


def read_tail(n: int) -> str:
    if not LOG_PATH.exists():
        return ""
    lines = LOG_PATH.read_text(errors="replace").splitlines()
    return "\n".join(lines[-n:]) if lines else ""


def cmd_status() -> None:
    if is_running():
        print("[OK ] процесс запущен, pid: " + pgrep().replace("\n", ", "))
    else:
        print("[-- ] процесс НЕ запущен")
    probe = run(
        [sys.executable, "-c",
         "from quiz_library.match import title_similarity as t; "
         "assert t(['безо'], ['безо']) == 1.0"],
        capture_output=True,
        text=True,
    )
    if probe.returncode == 0:
        print("quiz-library: свежая версия (match.py активен)")
    else:
        last = probe.stderr.strip().splitlines()
        print("quiz-library: свежая версия не установлена — "
              + (last[-1] if last else "?"))
    if LOG_PATH.exists():
        tail = read_tail(5)
        print("лог (последние 5): " + (" | ".join(tail.splitlines()) if tail else "<пуст>"))
    else:
        print(f"лог отсутствует ({LOG_PATH})")


def cmd_selfcheck() -> None:
    run([sys.executable, "-m", "alice_skill.self_check"], cwd=ROOT)


def cmd_start() -> None:
    if is_running():
        print("процесс уже запущен")
        return
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logf = open(LOG_PATH, "ab")
    subprocess.Popen(
        [sys.executable, "-m", PROC_MODULE],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=logf,
        start_new_session=True,
    )
    time.sleep(2)
    if is_running():
        print(f"запущен (pid {pgrep()}), лог: {LOG_PATH}")
    else:
        print("НЕ ПОДНЯЛСЯ — последние строки лога:")
        print(read_tail(25) or "<пуст>")


def cmd_stop() -> None:
    if not is_running():
        print("процесс не найден (уже остановлен)")
        return
    run(["pkill", "-f", PROC_PATTERN])
    time.sleep(1)
    if is_running():
        run(["pkill", "-9", "-f", PROC_PATTERN])
        time.sleep(1)
    print("остановлен" if not is_running() else "не удалось остановить")


def cmd_restart() -> None:
    cmd_stop()
    time.sleep(1)
    cmd_start()


def pip_quizlib() -> int:
    proc = run(
        [sys.executable, "-m", "pip", "install", "--force-reinstall", "--no-deps",
         QUIZLIB_SRC, "--quiet"],
        capture_output=True,
        text=True,
    )
    if proc.stderr.strip():
        print(proc.stderr.rstrip())
    return proc.returncode


def pip_check() -> bool:
    proc = run([sys.executable, "-m", "pip", "check"], capture_output=True, text=True)
    if proc.returncode == 0:
        print("   зависимости: OK")
        return True
    print("   КОНФЛИКТЫ ЗАВИСИМОСТЕЙ (pip check):")
    print(proc.stdout.rstrip())
    print(proc.stderr.rstrip())
    return False


def cmd_update() -> None:
    print("== git pull ==")
    pull = run(["git", "pull", "--ff-only"], cwd=ROOT)
    if pull.returncode != 0:
        print("git pull завершился с кодом " + str(pull.returncode) + " — прерываю")
        return
    print("== зависимости ==")
    aiohttp_pin = run(
        [sys.executable, "-m", "pip", "install", "--quiet", "aiohttp>=3.9.0,<3.12"],
        capture_output=True,
        text=True,
    )
    if aiohttp_pin.returncode != 0:
        print("pip install aiohttp завершился с ошибкой — прерываю")
        if aiohttp_pin.stderr.strip():
            print(aiohttp_pin.stderr.rstrip())
        return
    print("== переустановка quiz-library (--no-deps) ==")
    if pip_quizlib() != 0:
        print("pip install quiz-library завершился с ошибкой — прерываю")
        return
    if not pip_check():
        return
    probe = run(
        [sys.executable, "-c",
         "from quiz_library.match import title_similarity as t; "
         "assert t(['безо'], ['безо']) == 1.0"],
        capture_output=True,
    )
    if probe.returncode == 0:
        print("quiz-library: свежая версия")
    else:
        print("quiz-library: НЕ СВЕЖАЯ — прерываю рестарт")
        return
    time.sleep(1)
    cmd_stop()
    time.sleep(1)
    cmd_start()


def cmd_tail() -> None:
    if not LOG_PATH.exists():
        print(f"лог отсутствует ({LOG_PATH})")
        return
    print(read_tail(20) or "<пуст>")


MENU = [
    ("Статус", cmd_status),
    ("Self-check", cmd_selfcheck),
    ("Старт", cmd_start),
    ("Стоп", cmd_stop),
    ("Рестарт", cmd_restart),
    ("Обновить + старт", cmd_update),
    ("Хвост лога", cmd_tail),
    ("Выход", None),
]


def pause() -> bool:
    try:
        choice = input("\nEnter — в меню, q — выход: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return True
    return choice == "q"


def main() -> int:
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print("нужен терминал (tty) — запустите интерактивно")
        return 1
    selected = 0
    title = f"[Skill control] {ROOT}"
    footer = "\u2191/\u2193 \u2014 навигация \u00b7 Enter \u2014 выполнить \u00b7 q \u2014 выход"
    try:
        while True:
            sys.stdout.write(build_screen([label for label, _ in MENU], selected, title, footer))
            sys.stdout.flush()
            key = get_key()
            if key == "up":
                selected = (selected - 1) % len(MENU)
            elif key == "down":
                selected = (selected + 1) % len(MENU)
            elif key == "q":
                break
            elif key == "enter":
                label, fn = MENU[selected]
                if fn is None:
                    break
                sys.stdout.write(clear_screen() + f"== {label} ==\n")
                try:
                    fn()
                except Exception as exc:
                    print(f"ОШИБКА: {exc}")
                if pause():
                    break
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write(clear_screen())
    return 0


if __name__ == "__main__":
    sys.exit(main())