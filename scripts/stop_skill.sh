#!/usr/bin/env bash
# Останавливает процесс навыка, запущенный через nohup.
# Готово к вызову из update_and_start.sh (рестарт) и вручную:
#   bash scripts/stop_skill.sh
set -euo pipefail
cd "$(dirname "$0")/.."

if pgrep -f "alice_skill.skill" >/dev/null 2>&1; then
    pkill -f "alice_skill.skill" || true
    echo "навык остановлен"
else
    echo "процесс не найден (уже остановлен)"
fi

sleep 1
if pgrep -f "alice_skill.skill" >/dev/null 2>&1; then
    pkill -9 -f "alice_skill.skill" || true
    echo "пришлось убить принудительно (SIGKILL)"
fi