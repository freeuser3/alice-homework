# Дизайн навыка Алисы «Скажи домашку»

Дата: 2026-09-17
Статус: на ревью

## 1. Цель

Навык для Яндекс.Алисы, который по голосовой команде озвучивает домашнее
задание на следующий учебный день, получая данные из «Сетевого города» (СГО).

## 2. Вне области (YAGNI для v1)

- Оценки (следующая итерация).
- Расписание.
- Пагинация по предметам голосом.
- LLM-личность / свободный диалог.
- Мультиаккаунт и OAuth-привязка пользователей Яндекса.
- Карточки, картинки, галереи (цель — голосовая колонка).

## 3. Контекст и переиспользование

- **Форк `netschoolapi-plus`** (`git+https://github.com/freeuser3/netschool-api-plus.git`,
  версия 11.1.0) — асинхронный клиент СГО. Уже содержит фикс
  `Attachment.id` optional, нужный для `sgo.e-mordovia.ru`.
- **Логика домашек из тг-бота** (`C:\Users\max\Documents\Default Project`):
  `collect_homework`, `next_school_day`, сбор вложений — переиспользуется
  концептуально (копируется и адаптируется под пакет навыка).
- **aliceio** — фреймворк навыков Алисы (стиль aiogram 3.x): роутеры,
  `F`-фильтры, FSM, мидлвари, встроенное таймаут-событие.
- **API `netschool-api`** — не обязателен для навыка; навык работает с СГО
  напрямую через форк.

## 4. Архитектура (подход A)

Один asyncio-процесс: aiohttp-вебхук навыка + фоновый prefetch-воркер в том же
процессе. Кэш домашних заданий — in-memory, общий для воркера и вебхука.

```
Алиса ──HTTPS──▶ ngrok ──▶ aiohttp webhook (aliceio Dispatcher)
                                   │ читает
                                   ▼
                            HomeworkCache (in-memory)
                                   ▲ пишет
                                   │
                     prefetch worker (asyncio.Task)
                                   │ async
                                   ▼
                        netschoolapi-plus ──▶ СГО
```

Обоснование: для одного ученика не нужны Redis и отдельный процесс. Кэш в
памяти даёт нулевую задержку чтения и максимальную простоту.

## 5. Структура проекта

```
alice-homework/
├── alice_skill/
│   ├── __init__.py
│   ├── skill.py          # точка входа: Dispatcher, Skill, aiohttp, запуск воркера
│   ├── config.py         # загрузка config.json + env-overrides секретов
│   ├── cache.py          # HomeworkCache
│   ├── sgo.py            # async-доступ к СГО через netschoolapi-plus
│   ├── homework.py       # сбор + форматирование ДЗ под голос (TTS)
│   └── handlers/
│       ├── __init__.py
│       ├── start.py      # session.new → приветствие
│       ├── homework.py   # «домашка/дз/что задали» → из кэша
│       ├── more.py       # «дальше» → отдать догруженный результат
│       └── fallback.py   # непонятная команда → подсказка
├── tests/
├── requirements.txt
├── config.example.json
├── .gitignore
└── README.md
```

## 6. Компоненты

### 6.1 `config.py`
Читает `config.json` (gitignored). Поля:
- `sgo`: `login`, `password`, `school`
- `prefetch_interval` (сек, по умолчанию 1800)
- `host`, `port` (по умолчанию `127.0.0.1:8000`)
- `skill_id` (id навыка из консоли Диалогов)

Секреты (`sgo.login`, `sgo.password`, `skill_id`) можно переопределить
env-переменными. Ключей и паролей в коде нет.

### 6.2 `cache.py`
```python
@dataclass
class HomeworkCache:
    target_date: datetime.date | None
    text: str
    fetched_at: datetime.datetime | None
    status: Literal["ok", "empty", "error"]
```
Методы: `get()` (вернуть текущее значение), `set(...)`, `is_stale(ttl)`.

### 6.3 `sgo.py`
Асинхронная обёртка над `NetSchoolAPI`:
- `async def fetch_homework(login, password, school) -> HomeworkResult`
- Логин → `diary(start=tomorrow, end=tomorrow+7)` → `next_school_day` →
  `collect_homework` для целевого дня → форматирование.
- `finally`: `logout()`.
- Все исключения перехватываются, возвращается статус `error` с текстом.

### 6.4 `homework.py`
- `collect_homework(diary, target)` — список записей (предмет, задание, вложения).
- `next_school_day(diary, target)` — ближайший день с расписанием.
- `format_for_voice(entries) -> str` — плоский текст без HTML/эмодзи,
  пригодный для TTS. Вложения — словами («с вложением»).

### 6.5 `handlers/`
- **start.py**: `@router.message(F.session.new)` → приветствие + подсказка
  команд.
- **homework.py**: фильтр по вхождению подстрок «домашк», «дз», «что задали»,
  «задани». Ответ из кэша:
  - `ok` → текст ДЗ;
  - `empty` → «На завтра заданий нет»;
  - `error`/пусто → premature response + фоновая догрузка (см. §8).
- **more.py**: «дальше» → если есть догруженный результат, отдать его; иначе
  обычная подсказка.
- **fallback.py**: любое сообщение без совпадения → подсказка команд.

## 7. Prefetch worker

- Запускается в `@dispatcher.startup()` как `asyncio.Task`.
- Немедленный первый прогон, затем цикл с `prefetch_interval`.
- Каждый прогон: `fetch_homework(...)` → `cache.set(...)`.
- Останавливается в `@dispatcher.shutdown()` (отмена задачи).
- Ошибки СГО логируются, статус в кэше `error`, воркер не падает.

## 8. Обработка лимита 4.5 секунды

1. **Кэш-first**: хэндлер отвечает из кэша мгновенно.
2. **Premature response при промахе**: если кэш пуст/протух, хэндлер
   запускает `asyncio.create_task(refresh)` и возвращает «Секунду, посмотрю…
   скажи дальше», помечая ожидание в FSM.
3. **Timeout-страховка**: `Dispatcher(response_timeout=4)` и
   `@router.timeout()` возвращают короткую фразу; сессия не рвётся.
4. Refresh-задача складывает результат в кэш → на «дальше» отдаётся
   готовый текст.

## 9. Обработка ошибок

- `try/except` вокруг сетевых вызовов; пользователю — короткая вежливая фраза,
  в лог — трассировка.
- `@router.error()` — глобальный перехватчик непредвиденных исключений.
- Логи навыка пишутся в stdout/файл (для journalctl/systemd).

## 10. Конфигурация и секреты

- `config.json` в `.gitignore`; в репозитории — `config.example.json`.
- Секреты переопределяются переменными окружения в проде.

## 11. Развёртывание

- Debian-сервер v189239, отдельный venv
  `~/pyt/alice-homework/.venv`.
- Зависимости: `aliceio`, `aiohttp`, `netschoolapi-plus @ git+...`,
  `pytest` (dev).
- Запуск: процесс навыка, наружу — через **ngrok** (валидный HTTPS).
  URL вебхука (ngrok + `/alice`) прописывается в консоли навыка Диалогов.
- Опционально: systemd-юнит для автозапуска и логов в `journalctl`.
- Внимание: у бесплатного ngrok URL может меняться при перезапуске —
  тогда нужно обновить адрес в консоли навыка. При наличии домена позже —
  nginx + Let's Encrypt.

## 12. Тестирование

pytest, сеть мокается:
- `test_homework.py` — `collect_homework`, `next_school_day`,
  `format_for_voice` (в т.ч. пустой день, вложения, длинные списки).
- `test_cache.py` — статусы, TTL/протухание, пустое значение.
- `test_handlers.py` — ответ из кэша, промах запускает refresh,
  фразы timeout/fallback.

## 13. Открытые вопросы

- Точный набор фраз-интентов (расширять по мере использования).
- Формат фразы при «пустом» дне (каникулы/нет расписания).
- Нужен ли systemd сразу или запуск вручную, как у тг-бота.
