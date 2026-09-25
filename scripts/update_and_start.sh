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
# Версия quiz-library не поднимается между коммитами, поэтому pip не видит
# обновления по constraints — ставим принудительно последний HEAD.
pip install --force-reinstall "git+https://github.com/freeuser3/quiz-library.git" --quiet

echo "== проверка свежей версии =="
python -c "from quiz_library.match import title_similarity as t; assert t(['безо'], ['безо']) == 1.0"
echo "   quiz-library свежая (match.py присутствует)"

echo "== restart =="
bash scripts/stop_skill.sh

nohup .venv/bin/python -m alice_skill.skill > /tmp/alice-homework.log 2>&1 &
sleep 2
if pgrep -f "alice_skill.skill" >/dev/null 2>&1; then
    echo "навык запущен (лог: /tmp/alice-homework.log)"
else
    echo "ПРОЦЕСС НЕ ПОДНЯЛСЯ — смотрите /tmp/alice-homework.log"
    exit 1
fi