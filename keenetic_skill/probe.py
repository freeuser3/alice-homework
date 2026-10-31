from __future__ import annotations

import argparse
import json
import threading
from pathlib import Path
from typing import Any

DEFAULT_LOG = "keenetic.log"
SENSITIVE_KEYS = {"access_token", "authorization", "oauth_token"}
_lock = threading.Lock()


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "***" if key.lower() in SENSITIVE_KEYS else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def write_record(log_path: str | Path, record: dict) -> None:
    line = json.dumps(record, ensure_ascii=False)
    with _lock:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def _short(value: Any) -> str:
    if not value:
        return "-"
    text = str(value)
    return text if len(text) <= 16 else text[:8] + "…" + text[-4:]


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _combo_value(value: Any) -> Any:
    try:
        hash(value)
    except TypeError:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _extract(record: dict) -> dict:
    body = _as_dict(record.get("body"))
    session = _as_dict(body.get("session"))
    user = _as_dict(session.get("user"))
    application = _as_dict(session.get("application"))
    meta = _as_dict(body.get("meta"))
    request = _as_dict(body.get("request"))
    return {
        "ts": record.get("ts", "-"),
        "user_id": user.get("user_id"),
        "app_id": application.get("application_id"),
        "legacy_user_id": session.get("user_id"),
        "client_id": meta.get("client_id"),
        "new": session.get("new"),
        "command": request.get("command", "-"),
        "original": request.get("original_utterance", "-"),
    }


def report(log_path: str | Path, full: bool = False) -> int:
    path = Path(log_path)
    if not path.exists():
        print(f"лог не найден: {path}")
        return 1
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if not isinstance(record, dict):
                continue
            try:
                rows.append(_extract(record))
            except (AttributeError, TypeError, ValueError):
                continue
    if not rows:
        print("в логе нет записей")
        return 1
    fmt = (lambda v: str(v) if v else "-") if full else _short
    headers = [
        "ts", "user_id", "app_id", "legacy_user_id", "client_id",
        "new", "command", "original",
    ]
    display_rows = []
    for row in rows:
        display = dict(row)
        for key in ("user_id", "app_id", "legacy_user_id", "client_id"):
            display[key] = fmt(row[key])
        display_rows.append(display)
    widths = {
        h: max(len(h), *(len(str(row[h])) for row in display_rows))
        for h in headers
    }
    print("  ".join(h.ljust(widths[h]) for h in headers))
    print("  ".join("-" * widths[h] for h in headers))
    for row in display_rows:
        print("  ".join(str(row[h]).ljust(widths[h]) for h in headers))
    combos = {}
    for row in rows:
        key = tuple(
            _combo_value(row[k]) for k in ("user_id", "app_id", "client_id")
        )
        combos[key] = combos.get(key, 0) + 1
    print("\nРазличных комбинаций user_id / app_id / client_id:", len(combos))
    for (user_id, app_id, client_id), count in combos.items():
        print(
            f"  user_id={fmt(user_id)}  app_id={fmt(app_id)}  "
            f"client_id={fmt(client_id)}  запросов={count}"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Отчёт по запросам Алисы к keenetic-endpoint"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    p_report = sub.add_parser("report", help="показать сравнение из лога")
    p_report.add_argument("--log", default=DEFAULT_LOG)
    p_report.add_argument(
        "--full",
        action="store_true",
        help="не сокращать идентификаторы",
    )
    args = parser.parse_args(argv)
    return report(Path(args.log), args.full)


if __name__ == "__main__":
    raise SystemExit(main())
