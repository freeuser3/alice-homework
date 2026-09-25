#!/usr/bin/env bash
# Обновляет код навыка (git pull), переустанавливает quiz-library из git
# и перезапускает процесс навыка под nohup.
#
# Data (subjects.json, digests/) признаются приватными и git'ом не живут;
# их переносят на сервер вручную (scp) ДО запуска этого скрипта.
#
# Запуск:
#   bash scripts/update_and_start.sh
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

echo "== git pull =="
git pull --ff-only

echo "== зависимости (quiz-library из git) =="
source .venv/bin/activate
# aiohttp должен быть совместим с aliceio (<3.12): прошлый --force-reinstall без
# --no-deps мог затащить 3.14.3, вернём совместимую версию.
pip install --quiet "aiohttp>=3.9.0,<3.12"
# Версия quiz-library не поднимается между коммитами, поэтому pip не видит
# обновления по constraints — ставим принудительно последний HEAD.
# --no-deps: не тянуть конфликтующие зависимости (aiohttp уже закреплён выше).
pip install --force-reinstall --no-deps "git+https://github.com/freeuser3/quiz-library.git" --quiet

echo "== проверка целостности окружения (pip check) =="
if pip check >/tmp/pip-check.log 2>&1; then
    echo "   зависимости: OK"
else
    echo "   КОНФЛИКТЫ ЗАВИСИМОСТЕЙ:"
    cat /tmp/pip-check.log
    exit 1
fi

echo "== проверка свежей версии =="
python -c "from quiz_library.match import title_similarity as t; assert t(['безо'], ['безо']) == 1.0"
echo "   quiz-library свежая (match.py присутствует)"

echo "== restart =="
bash scripts/stop_skill.sh

nohup .venv/bin/python -m alice_skill.skill > /dev/null 2>> /tmp/alice-homework.log &
sleep 2
if pgrep -f "alice_skill.skill" >/dev/null 2>&1; then
    echo "навык запущен (лог: /tmp/alice-homework.log)"
else
    echo "ПРОЦЕСС НЕ ПОДНЯЛСЯ — смотрите /tmp/alice-homework.log"
    exit 1
fi