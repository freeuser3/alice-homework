# Скажи домашку

Yandex Alice voice skill that reads tomorrow's homework from СГО
(e-mordovia.ru). Runs as a single aiohttp process with an in-memory
cache and a background prefetch worker.

## Architecture

```
Alice → HTTPS (ngrok) → aiohttp webhook (aliceio Dispatcher)
                              ↓ reads
                         HomeworkCache (in-memory)
                              ↑ writes
                    PrefetchWorker (asyncio.Task)
                              ↓ async
                    netschoolapi-plus → СГО
```

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate     # Windows
source .venv/bin/activate  # Linux
pip install -r requirements.txt
cp config.example.json config.json
# edit config.json with your СГО credentials and skill ID
python -m alice_skill.skill
```

## Deploy (Debian)

```bash
python3 -m venv ~/pyt/alice-homework/.venv
source ~/pyt/alice-homework/.venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json
# edit config.json
nohup python -m alice_skill.skill > /tmp/alice-homework.log 2>&1 &

# In another terminal:
ngrok http 8000
# Copy the HTTPS URL → Dialogs Console → webhook:
#   https://<ngrok-id>.ngrok.io/alice
```

## Config

`config.json` (gitignored — use `config.example.json`):

| Key | Description | Default |
|-----|-------------|---------|
| `sgo.login` | СГО login (or `SGO_LOGIN` env) | — |
| `sgo.password` | СГО password (or `SGO_PASSWORD` env) | — |
| `sgo.school` | School name (or `SGO_SCHOOL` env) | — |
| `skill_id` | Dialogs skill ID (or `SKILL_ID` env) | — |
| `prefetch_interval` | Seconds between background fetches | `1800` |
| `host` | aiohttp bind address | `127.0.0.1` |
| `port` | aiohttp bind port | `8000` |

## Testing

```bash
pytest -v
```
