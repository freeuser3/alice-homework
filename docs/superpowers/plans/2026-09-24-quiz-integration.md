# Голосовая викторина в навыке «Скажи домашку» — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить в навык «Скажи домашку» голосовую викторину: команда «спроси по географии» берёт запись из кэша домашки, генерирует один вопрос через quiz-library и озвучивает его (с fallback на «дальше» при медленной генерации).

**Architecture:** Подход A из спеки: тонкая обвязка без FSM. Новый роутер `quiz_router` + отложенный слот `QuizSlot` (в `workflow_data`, как cache/worker). Пробуем ответить сразу (бюджет 3.5 с, `asyncio.wait` без отмены); не уложились — «Секунду, придумываю вопрос…», вопрос приходит по «дальше» (слот приоритетнее домашки). Конфиг квиза опционален: без LLM-ключа навык работает как раньше.

**Tech Stack:** Python 3.11+, aliceio 0.2.3, aiohttp, quiz-library (git+https из GitHub), pytest (без pytest-asyncio-режима auto — тесты асинхронные помечаются `@pytest.mark.asyncio`).

**Spec:** `docs/superpowers/specs/2026-09-24-quiz-integration-design.md` + базовое `docs/superpowers/specs/2026-09-17-alice-homework-design.md`.
Точки интеграции с уже опубликованной библиотекой (quiz-library, v1):
- `quiz_library.model.HomeworkEntry` — `@dataclass`, поля `subject: str`, `content: str`.
- `quiz_library.service.QuizService.from_config(subjects_path: str|Path, llm: LLMClient)` — строит `QuizService` (registry загружается сразу; отсутствие/порча файла → исключение OSError/ValueError/KeyError).
- `QuizService.querying API`: `patterns_for(subject) -> list[str]`, `find_entry(entries: list[HomeworkEntry], subject) -> HomeworkEntry|None`, `async question_for(entry) -> Question|None` (LLMError внутри уже превращается в None).
- `quiz_library.llm.LLMClient(LLMConfig(base_url, api_key, model, timeout))` — сессия aiohttp создаётся лениво (создание клиента безопасно вне event loop); `await client.close()`.
- `quiz_library.model.Question` — `subject, paragraph, paragraph_title, pages, text`.
- `quiz_library.parser.parse_paragraph(text, patterns) -> int|None`.

## Global Constraints

- Конфиг квиза опционален: `load_config` по-прежнему бросает `ValueError` только при отсутствии SGO-кредов или `skill_id`; отсутствие `llm`-блока/ключа НЕ валидируется при старте.
- Смена `LLM_MODEL` — правка одной строки конфига/`config.example.json`; дефолт `gpt-4.1-nano`, никаких новых SDK.
- `HomeworkResult.entries` — поле с `field(default_factory=list)` (существующие конструкции `HomeworkResult(status, target_date, text[, error])` не ломаются).
- Никаких реальных выжимок в тестах навыка и в git (приватные данные): quiz-library в тестах навыка фейкится.
- Фразы русские, точно как в спеках (см. тексты в задачах); не менять существующие `PREMATURE_TEXT/HINT_TEXT/TIMEOUT_TEXT/ERROR_TEXT`.
- Репо на ветке `master`; зависимости: `pip install -r requirements.txt` (после Task «requirements») в тестовом окружении репо. Запуск: `python -m pytest <path>` из корня `alice-homework`.
- `parse_paragraph` в навык приходит из quiz-library; усечения/паттернов навык не дублирует.

## Review Focus

1. «спроси по географии» при пустом кэше (entries нет вообще) → вежливая фраза «Сегодня ничего не задано», не падение. → тест в Task 5.
2. Регистр в команде и в конфиге («География» в subjects.json vs «география»/«ГЕОГРАФИЯ» в команде) → совпадение case-insensitive. → тест в Task 5.
3. Конфиг без LLM (quiz=None) → «Викторина не настроена», остальные команды (домашка/дальше/fallback) работают как раньше. → тесты Task 5 и Task 7.
4. Генерация не уложилась в окно: слот живой, повторный триггер того же предмета не порождает второй вызов (single-flight), «дальше» пока вопрос не готов — «Ещё чуть-чуть…». → тесты Task 5 и Task 6.
5. Генерация завершилась ошибкой: вопрос не появился, слот очищен, повторное «дальше» отдаёт домашку. → тест Task 6.

---

### Task 1: Конфигурационный блок квиза (LlmConfig, subjects_path, optional)

**Files:**
- Modify: `alice_skill/config.py` (весь файл)
- Modify: `config.example.json` (добавить пример llm-блока, без ключа)
- Modify: `.gitignore` (добавить `digests/`, `subjects.json`, `_q.txt`)
- Test: `tests/test_config.py:15-70` (добавить тесты)

**Interfaces:**
- Consumes: текущий `Config`/`load_config` из `alice_skill/config.py`.
- Produces:
  - `LlmConfig` (frozen dataclass): `base_url: str = "https://api.dslab.tech/v1"`, `api_key: str = ""`, `model: str = "gpt-4.1-nano"`, `timeout: float = 20.0`.
  - `Config` += `subjects_path: str = "subjects.json"`, `llm: LlmConfig | None = None`.
  - `load_config(path) -> Config`: env-оверрайды `LLM_BASE_URL/LLM_API_KEY/LLM_MODEL/LLM_TIMEOUT/SUBJECTS_PATH`; `llm is None`, если нет ни env-ключа, ни `raw["llm"]["api_key"]`.
  - `config.example.json` и `.gitignore` обновляются.

- [ ] **Step 1: Write the failing tests**

Добавить в `tests/test_config.py` в конец файла:

```python
def test_load_config_llm_block(tmp_path):
    path = _write_config(tmp_path, {
        "sgo": {"login": "u", "password": "p", "school": "s"},
        "skill_id": "sid",
        "subjects_path": "configs/subjects.json",
        "llm": {"base_url": "https://api.dslab.tech/v1", "api_key": "sk-x",
                "model": "deepseek-v4-flash", "timeout": 30},
    })
    cfg = load_config(path)
    assert cfg.subjects_path == "configs/subjects.json"
    assert cfg.llm is not None
    assert cfg.llm.api_key == "sk-x"
    assert cfg.llm.model == "deepseek-v4-flash"
    assert cfg.llm.timeout == 30


def test_load_config_llm_defaults(tmp_path):
    path = _write_config(tmp_path, {
        "sgo": {"login": "u", "password": "p", "school": "s"},
        "skill_id": "sid",
        "llm": {"api_key": "sk-x"},
    })
    cfg = load_config(path)
    assert cfg.llm is not None
    assert cfg.llm.base_url == "https://api.dslab.tech/v1"
    assert cfg.llm.model == "gpt-4.1-nano"
    assert cfg.llm.timeout == 20.0


def test_load_config_llm_optional(tmp_path):
    path = _write_config(tmp_path, {
        "sgo": {"login": "u", "password": "p", "school": "s"},
        "skill_id": "sid",
    })
    cfg = load_config(path)
    assert cfg.llm is None
    assert cfg.subjects_path == "subjects.json"


def test_load_config_llm_env_overrides(tmp_path, monkeypatch):
    path = _write_config(tmp_path, {
        "sgo": {"login": "u", "password": "p", "school": "s"},
        "skill_id": "sid",
        "llm": {"api_key": "sk-file"},
    })
    monkeypatch.setenv("LLM_API_KEY", "sk-env")
    monkeypatch.setenv("LLM_MODEL", "gpt-4.1-nano")
    monkeypatch.setenv("SUBJECTS_PATH", "/tmp/subj.json")
    cfg = load_config(path)
    assert cfg.llm is not None
    assert cfg.llm.api_key == "sk-env"
    assert cfg.subjects_path == "/tmp/subj.json"


def test_load_config_llm_disabled_when_only_base_url(tmp_path):
    path = _write_config(tmp_path, {
        "sgo": {"login": "u", "password": "p", "school": "s"},
        "skill_id": "sid",
        "llm": {"base_url": "https://api.dslab.tech/v1"},
    })
    cfg = load_config(path)
    assert cfg.llm is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config.py -q`
Expected: FAIL («object» has no attribute «llm» / not present)

- [ ] **Step 3: Implement config**

В `alice_skill/config.py`:

```python
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SgoConfig:
    login: str
    password: str
    school: str


@dataclass(frozen=True)
class LlmConfig:
    base_url: str = "https://api.dslab.tech/v1"
    api_key: str = ""
    model: str = "gpt-4.1-nano"
    timeout: float = 20.0


@dataclass(frozen=True)
class Config:
    sgo: SgoConfig
    skill_id: str
    prefetch_interval: int = 1800
    host: str = "127.0.0.1"
    port: int = 8000
    subjects_path: str = "subjects.json"
    llm: LlmConfig | None = None


def load_config(path: str | Path = "config.json") -> Config:
    with open(path, encoding="utf-8") as f:
        raw: dict = json.load(f)

    sgo_raw: dict = raw.get("sgo", {})
    sgo = SgoConfig(
        login=os.environ.get("SGO_LOGIN") or sgo_raw.get("login", ""),
        password=os.environ.get("SGO_PASSWORD") or sgo_raw.get("password", ""),
        school=os.environ.get("SGO_SCHOOL") or sgo_raw.get("school", ""),
    )
    if not (sgo.login and sgo.password and sgo.school):
        raise ValueError(
            "sgo.login, sgo.password, sgo.school must be set in config.json "
            "or via SGO_LOGIN / SGO_PASSWORD / SGO_SCHOOL env vars"
        )

    skill_id = os.environ.get("SKILL_ID") or raw.get("skill_id", "")
    if not skill_id:
        raise ValueError("skill_id must be set in config.json or SKILL_ID env var")

    prefetch = int(os.environ.get("PREFETCH_INTERVAL") or raw.get("prefetch_interval", 1800))
    host = raw.get("host", "127.0.0.1")
    port = int(raw.get("port", 8000))
    subjects_path = os.environ.get("SUBJECTS_PATH") or raw.get("subjects_path", "subjects.json")

    llm_raw: dict = raw.get("llm", {}) or {}
    api_key = os.environ.get("LLM_API_KEY") or llm_raw.get("api_key", "")
    llm = None
    if api_key:
        llm = LlmConfig(
            base_url=os.environ.get("LLM_BASE_URL")
            or llm_raw.get("base_url", "https://api.dslab.tech/v1"),
            api_key=api_key,
            model=os.environ.get("LLM_MODEL") or llm_raw.get("model", "gpt-4.1-nano"),
            timeout=float(os.environ.get("LLM_TIMEOUT") or llm_raw.get("timeout", 20.0)),
        )

    return Config(
        sgo=sgo, skill_id=skill_id, prefetch_interval=prefetch,
        host=host, port=port, subjects_path=subjects_path, llm=llm,
    )
```

В `config.example.json` после `"skill_id"` добавить (ключ НЕ вписывать):

```json
  "subjects_path": "subjects.json",
  "llm": {
    "base_url": "https://api.dslab.tech/v1",
    "api_key": "ВАШ_DSLAB_КЛЮЧ",
    "model": "gpt-4.1-nano",
    "timeout": 20
  }
```

В `.gitignore` добавить строки (если их ещё нет): `digests/`, `subjects.json`, `_q.txt`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_config.py -q`
Expected: PASS (11 passed)

- [ ] **Step 5: Commit**

```bash
git add alice_skill/config.py config.example.json .gitignore tests/test_config.py
git commit -m "feat: optional quiz config (llm block, subjects_path)"
```

---

### Task 2: Кэш хранит записи предметов (HomeworkResult.entries)

**Files:**
- Modify: `alice_skill/sgo.py:22-27` (HomeworkResult), `alice_skill/sgo.py:47-54` (fetch_homework)
- Modify: `alice_skill/homework.py` (конец файла: helper `homework_entries`)
- Test: `tests/test_sgo.py`, `tests/test_homework.py`

**Interfaces:**
- Consumes: `HomeworkResult` (существующие поля), `collect_homework` dict-записи (ключи `subject`, `content`).
- Produces:
  - `HomeworkResult.entries: list[HomeworkEntry] = field(default_factory=list)` (тип из quiz-library).
  - `homework_entries(entries: list[dict]) -> list[HomeworkEntry]` в `alice_skill/homework.py` — `HomeworkEntry(subject=e["subject"], content=_clean_content(e["content"]))`.
  - `fetch_homework` заполняет `HomeworkResult.entries` результатом `homework_entries(entries)`.

- [ ] **Step 1: Write the failing tests**

В `tests/test_homework.py` (в конец):

```python
from alice_skill.homework import homework_entries


def test_homework_entries_builds_library_entries():
    raw = [
        {"subject": "География", "content": "<p>параграф 6</p>", "assignment_id": 1},
        {"subject": "Биология", "content": "§ 3, вопросы", "assignment_id": 2},
    ]
    result = homework_entries(raw)
    assert [e.subject for e in result] == ["География", "Биология"]
    assert result[0].content == "параграф 6"
    assert result[1].content == "§ 3, вопросы"
```

В `tests/test_sgo.py` (в конец, `_ok_result`-подобный хелпер уже есть — см. файл):

```python
def test_fetch_homework_result_keeps_entries():
    # добавь к существующему в файле набору фейков: FakeHomeworkResult не нужен —
    # проверяем только, что поле существует и по умолчанию пустое
    result = HomeworkResult(status="empty", target_date=None, text="")
    assert result.entries == []
```

(если в `tests/test_sgo.py` нет импорта `HomeworkResult` — добавить `from alice_skill.sgo import HomeworkResult`.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_homework.py tests/test_sgo.py -q`
Expected: FAIL (ImportError: cannot import name «homework_entries»; AttributeError: «entries»)

- [ ] **Step 3: Implement**

`alice_skill/homework.py` — в конец файла добавить (импорт `HomeworkEntry` сверху):

```python
from quiz_library.model import HomeworkEntry
```

```python
def homework_entries(entries: list[dict]) -> list[HomeworkEntry]:
    return [
        HomeworkEntry(subject=e["subject"], content=_clean_content(e["content"]))
        for e in entries
    ]
```

`alice_skill/sgo.py`:

```python
from dataclasses import dataclass, field
```

```python
@dataclass
class HomeworkResult:
    status: Literal["ok", "empty", "error"]
    target_date: datetime.date | None
    text: str
    error: str | None = None
    entries: list[HomeworkEntry] = field(default_factory=list)
```

и импорт `from quiz_library.model import HomeworkEntry`.

В `fetch_homework` (строка с конструкцией результата «ok»):

```python
        text = format_for_voice(entries, day, today=today)
        status = "ok" if entries else "empty"
        return HomeworkResult(
            status=status, target_date=day, text=text,
            entries=homework_entries(entries),
        )
```

и импорт `homework_entries` в блоке `from alice_skill.homework import (...)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_homework.py tests/test_sgo.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add alice_skill/homework.py alice_skill/sgo.py tests/test_homework.py tests/test_sgo.py
git commit -m "feat: keep structured homework entries in HomeworkResult"
```

---

### Task 3: QuizSlot (состояние викторины)

**Files:**
- Create: `alice_skill/quiz_state.py`
- Test: `tests/test_quiz_state.py`

**Interfaces:**
- Consumes: ничего (чистый dataclass).
- Produces:
  - `QuizSlot` (dataclass): поля `subject: str | None = None`, `paragraph: int | None = None`, `question: str | None = None`, `task: asyncio.Task | None = None`.
  - Методы: `set_pending(subject: str, paragraph: int, task: asyncio.Task)` — фиксирует subject/paragraph/task, обнуляет question; `finish(subject: str, question: str | None)` — заполняет question ТОЛЬКО если текущая задача вызвана (защита от фоновой задачи, устаревшей к моменту завершения); `clear()` — обнуляет все поля; свойство `has_pending() -> bool`.

- [ ] **Step 1: Write the failing tests**

`tests/test_quiz_state.py`:

```python
import asyncio

import pytest

from alice_skill.quiz_state import QuizSlot


async def _finish_now(slot, subject, question):
    slot.finish(subject, question)


@pytest.mark.asyncio
async def test_set_pending_and_finish():
    slot = QuizSlot()
    task = asyncio.create_task(_finish_now(slot, "География", "Какой газопровод важнее?"))
    slot.set_pending(subject="География", paragraph=6, task=task)
    assert slot.task is task
    assert slot.has_pending is True
    await task  # внутри task'а: slot.task is current_task → вопрос записывается
    assert slot.question == "Какой газопровод важнее?"
    assert slot.has_pending is True


@pytest.mark.asyncio
async def test_finish_ignores_stale_task():
    slot = QuizSlot()
    old_task = asyncio.create_task(_finish_now(slot, "География", "старый вопрос"))
    slot.set_pending(subject="География", paragraph=6, task=old_task)
    # «протухший» фоновый таск заканчивается, а слот уже переключён на новый — вызов из теста
    # не совпадает с slot.task (current_task — корутина теста), вопрос должен игнорироваться
    new_task = asyncio.create_task(asyncio.sleep(0))
    slot.set_pending(subject="Биология", paragraph=3, task=new_task)
    assert slot.paragraph == 3
    old_task.cancel()
    await asyncio.sleep(0)  # даём старому таску «упасть»
    slot.finish("География", "старый вопрос")
    assert slot.question is None
    assert slot.subject == "Биология"
    await new_task


def test_clear_resets_all():
    slot = QuizSlot()
    slot.subject = "География"
    slot.paragraph = 6
    slot.question = "Вопрос"
    slot.clear()
    assert slot.subject is None
    assert slot.paragraph is None
    assert slot.question is None
    assert slot.task is None
    assert slot.has_pending is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_quiz_state.py -q`
Expected: FAIL (ModuleNotFoundError: quiz_state)

- [ ] **Step 3: Implement**

`alice_skill/quiz_state.py`:

```python
"""Отложенное состояние викторины: слот «подумать-и-ответь-по-дальше»."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass


@dataclass
class QuizSlot:
    subject: str | None = None
    paragraph: int | None = None
    question: str | None = None
    task: asyncio.Task | None = None

    def set_pending(self, subject: str, paragraph: int, task: asyncio.Task) -> None:
        self.subject = subject
        self.paragraph = paragraph
        self.task = task
        self.question = None

    def finish(self, subject: str, question: str | None) -> None:
        if self.task is not None and self.task is asyncio.current_task():
            self.subject = subject
            self.question = question

    def clear(self) -> None:
        self.subject = None
        self.paragraph = None
        self.question = None
        self.task = None

    @property
    def has_pending(self) -> bool:
        return self.task is not None or self.question is not None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_quiz_state.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add alice_skill/quiz_state.py tests/test_quiz_state.py
git commit -m "feat: QuizSlot pending-question state"
```

---

### Task 4: QuizBundle (ленивая обвязка над quiz-library)

**Files:**
- Create: `alice_skill/quiz_service.py`
- Test: `tests/test_quiz_service.py`

**Interfaces:**
- Consumes: `Config` (Task 1), `quiz_library.service.QuizService`, `quiz_library.llm.LLMClient`, `quiz_library.model.LLMConfig`.
- Produces:
  - `build_quiz(cfg: Config) -> QuizBundle | None` — None при `cfg.llm is None or not cfg.llm.api_key`; иначе конструирует `LLMClient` и `QuizBundle`.
  - `QuizBundle` (dataclass): `cfg`, `llm: LLMClient`, приватные `_service/_names/_built`.
    - `service() -> QuizService | None` — лениво и один раз: `QuizService.from_config(cfg.subjects_path, self.llm)` + чтение имён предметов из `cfg.subjects_path` (топ-уровневые ключи JSON). При `(OSError, ValueError, KeyError, TypeError)` → логирует warning и возвращает None.
    - `subject_names -> list[str]` — останавливает загрузку через `service()` и возвращает имена.
    - `async close()` — `await self.llm.close()`.

- [ ] **Step 1: Write the failing tests**

`tests/test_quiz_service.py`:

```python
import json

import pytest

from alice_skill.config import Config, LlmConfig, SgoConfig
from alice_skill.quiz_service import QuizBundle, build_quiz


def _cfg(tmp_path, *, api_key="sk-x", subjects="subjects.json") -> Config:
    return Config(
        sgo=SgoConfig(login="u", password="p", school="s"),
        skill_id="sid",
        subjects_path=str(tmp_path / subjects),
        llm=LlmConfig(api_key=api_key),
    )


def test_build_quiz_none_without_llm(tmp_path):
    cfg = Config(sgo=SgoConfig(login="u", password="p", school="s"), skill_id="sid")
    assert build_quiz(cfg) is None


def test_build_quiz_none_without_api_key(tmp_path):
    assert build_quiz(_cfg(tmp_path, api_key="")) is None


def test_build_quiz_returns_bundle(tmp_path):
    bundle = build_quiz(_cfg(tmp_path))
    assert bundle is not None
    assert bundle.service() is None  # subjects.json ещё нет


def test_service_and_subject_names(tmp_path):
    subjects_path = tmp_path / "subjects.json"
    subjects_path.write_text(
        json.dumps({"География": {"digest": "digests/geografia.json",
                                  "paragraph_patterns": ["параграф", "§"]}}),
        encoding="utf-8",
    )
    bundle = build_quiz(_cfg(tmp_path, subjects=subjects_path.name))
    assert bundle is not None
    svc = bundle.service()
    assert svc is not None
    assert bundle.subject_names == ["География"]
    assert bundle.service() is svc  # лениво, один раз


def test_broken_subjects_json_yields_none(tmp_path):
    bad = tmp_path / "subjects.json"
    bad.write_text("{not json", encoding="utf-8")
    bundle = build_quiz(_cfg(tmp_path, subjects=bad.name))
    assert bundle is not None
    assert bundle.service() is None
    assert bundle.subject_names == []


@pytest.mark.asyncio
async def test_close_awaits_llm_close(tmp_path):
    bundle = build_quiz(_cfg(tmp_path))
    assert bundle is not None
    await bundle.close()  # не падает; session не создавалась
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_quiz_service.py -q`
Expected: FAIL (ModuleNotFoundError: quiz_service)

- [ ] **Step 3: Implement**

`alice_skill/quiz_service.py`:

```python
"""Ленивая сборка QuizService (quiz-library) из Config навыка."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from quiz_library.llm import LLMClient
from quiz_library.model import LLMConfig
from quiz_library.service import QuizService

from alice_skill.config import Config

logger = logging.getLogger(__name__)


@dataclass
class QuizBundle:
    cfg: Config
    llm: LLMClient
    _service: QuizService | None = None
    _names: list[str] = field(default_factory=list)
    _built: bool = False

    def service(self) -> QuizService | None:
        if self._built:
            return self._service
        self._built = True
        try:
            self._service = QuizService.from_config(self.cfg.subjects_path, self.llm)
            with open(self.cfg.subjects_path, encoding="utf-8") as f:
                self._names = list(json.load(f).keys())
        except (OSError, ValueError, KeyError, TypeError) as exc:
            logger.warning("quiz not configured: %s", exc)
            self._service = None
            self._names = []
        return self._service

    @property
    def subject_names(self) -> list[str]:
        self.service()
        return self._names

    async def close(self) -> None:
        await self.llm.close()


def build_quiz(cfg: Config) -> QuizBundle | None:
    if cfg.llm is None or not cfg.llm.api_key:
        return None
    llm = LLMClient(
        LLMConfig(cfg.llm.base_url, cfg.llm.api_key, cfg.llm.model, cfg.llm.timeout)
    )
    return QuizBundle(cfg=cfg, llm=llm)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_quiz_service.py -q`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add alice_skill/quiz_service.py tests/test_quiz_service.py
git commit -m "feat: lazy QuizBundle over quiz-library"
```

---

### Task 5: quiz_router — «спроси/проверь по …»

**Files:**
- Create: `alice_skill/handlers/quiz.py`
- Test: `tests/test_quiz_handlers.py`

**Interfaces:**
- Consumes: `QuizBundle` (Task 4), `QuizSlot` (Task 3), `cache`/`HomeworkCache`, quiz-library `Question`/`parse_paragraph`.
- Produces:
  - `quiz_router` (Router), фильтр `QUIZ_FILTER`.
  - `handle_quiz(message, cache, quiz, slot) -> Response` (шаблонные имена совпадают с ключами workflow_data).
  - Константы (используются также Task 6): `QUIZ_NOT_CONFIGURED_TEXT`, `NO_HOMEWORK_TEXT`, `ASK_SUBJECT_TEXT`, `NO_PARAGRAPH_TEXT`, `PREMATURE_QUIZ_TEXT`, `PREMATURE_MORE_TEXT`, `QUIZ_FAIL_TEXT`.
  - Вспомогательная `_quiz_task(service, entry, slot)` — асинхронная обёртка, вызывающая `service.question_for(entry)` и `slot.finish(...)`; завернутый таск и есть `slot.task`.

Поток (спека §6): (1) `quiz is None` или `service()` вернул None → «Викторина не настроена»; (2) entries пусты → «Сегодня ничего не задано»; (3) предмет из команды (case-insensitive среди `quiz.subject_names`) или единственный предмет в entries, иначе при непустых entries → «По какому предмету спросить?»; (4) нет записи предмета → «По <предмет> ничего не задано»; (5) `parse_paragraph(entry.content, patterns)` None → «Не нашла параграф…»; (6) готовый question в слоте того же предмета → сразу (слот очищается); (7) уже идёт генерация того же (subject, paragraph) → повторно «Секунду…»; (8) иначе новый task + `asyncio.wait(timeout=DIRECT_TIMEOUT=3.5)`; уложился и вопрос есть → сразу, иначе «Секунду…».

- [ ] **Step 1: Write the failing tests**

`tests/test_quiz_handlers.py`:

```python
import asyncio
import datetime
from unittest.mock import MagicMock

import pytest

from alice_skill.cache import HomeworkCache
from alice_skill.handlers.quiz import (
    ASK_SUBJECT_TEXT,
    NO_HOMEWORK_TEXT,
    NO_PARAGRAPH_TEXT,
    PREMATURE_QUIZ_TEXT,
    QUIZ_FAIL_TEXT,
    QUIZ_NOT_CONFIGURED_TEXT,
    handle_quiz,
)
from alice_skill.quiz_state import QuizSlot
from quiz_library.model import HomeworkEntry, Question


def _entry(content="параграф 6", subject="География"):
    return HomeworkEntry(subject=subject, content=content)


def _cache(*entries):
    cache = HomeworkCache()
    if entries:
        cache.set(MagicMock(status="ok", entries=list(entries)))
    return cache


class _FakeService:
    def __init__(self, question_for=None, patterns=("параграф", "§")):
        self.question_for = question_for or self._async_none
        self.patterns = patterns
        self.entries = None

    async def _async_none(self, entry):
        return None

    def patterns_for(self, subject):
        return list(self.patterns)

    def find_entry(self, entries, subject):
        for e in entries:
            if e.subject.lower() == subject.lower():
                return e
        return None


def _bundle(service):
    b = MagicMock()
    b.service.return_value = service
    type(b).subject_names = property(lambda self: ["География", "Биология"])
    return b


@pytest.mark.asyncio
async def test_not_configured_when_quiz_missing():
    cache = _cache(_entry())
    slot = QuizSlot()
    resp = await handle_quiz(
        MagicMock(command="спроси по географии"), cache=cache, quiz=None, slot=slot,
    )
    assert resp.text == QUIZ_NOT_CONFIGURED_TEXT


@pytest.mark.asyncio
async def test_not_configured_when_subjects_missing():
    b = MagicMock()
    b.service.return_value = None
    cache = _cache(_entry())
    resp = await handle_quiz(
        MagicMock(command="спроси по географии"), cache=cache, quiz=b, slot=QuizSlot(),
    )
    assert resp.text == QUIZ_NOT_CONFIGURED_TEXT


@pytest.mark.asyncio
async def test_no_entries():
    cache = _cache()
    b = _bundle(_FakeService())
    resp = await handle_quiz(
        MagicMock(command="спроси по географии"), cache=cache, quiz=b, slot=QuizSlot(),
    )
    assert "ничего не задано" in resp.text.lower()


@pytest.mark.asyncio
async def test_no_entry_for_subject():
    cache = _cache(_entry(subject="Биология"))
    b = _bundle(_FakeService())
    resp = await handle_quiz(
        MagicMock(command="спроси по географии"), cache=cache, quiz=b, slot=QuizSlot(),
    )
    # предмет найден по основе, но записи по нему нет
    assert "ничего не задано" in resp.text.lower()
    assert "география" in resp.text.lower()


@pytest.mark.asyncio
async def test_case_insensitive_subject():
    cache = _cache(_entry())
    b = _bundle(_FakeService())
    resp = await handle_quiz(
        MagicMock(command="спроси по ГЕОГРАФИИ"), cache=cache, quiz=b, slot=QuizSlot(),
    )
    # предмет найден; вопрос не задан (fake возвращает None)
    assert resp.text == QUIZ_FAIL_TEXT


@pytest.mark.asyncio
async def test_no_paragraph():
    cache = _cache(_entry(content="прочитать", subject="География"))
    b = _bundle(_FakeService())
    resp = await handle_quiz(
        MagicMock(command="спроси по географии"), cache=cache, quiz=b, slot=QuizSlot(),
    )
    assert "параграф" in resp.text


@pytest.mark.asyncio
async def test_ask_subject_when_many():
    cache = _cache(_entry(subject="География"), _entry(subject="Биология"))
    b = _bundle(_FakeService())
    resp = await handle_quiz(
        MagicMock(command="спроси"), cache=cache, quiz=b, slot=QuizSlot(),
    )
    assert resp.text == ASK_SUBJECT_TEXT


@pytest.mark.asyncio
async def test_immediate_answer():
    async def give(entry):
        return Question(subject="География", paragraph=6, paragraph_title="Газовая",
                        pages=(22, 25), text="Какой вопрос?")

    cache = _cache(_entry())
    b = _bundle(_FakeService(question_for=give))
    slot = QuizSlot()
    resp = await handle_quiz(
        MagicMock(command="спроси по географии"), cache=cache, quiz=b, slot=slot,
    )
    assert resp.text == "Какой вопрос?"
    assert slot.has_pending is False


@pytest.mark.asyncio
async def test_slow_answer_promises_question():
    release = asyncio.Event()

    async def slow(entry):
        await release.wait()
        return Question(subject="География", paragraph=6, paragraph_title="Газовая",
                        pages=(22, 25), text="Готовый вопрос.")

    cache = _cache(_entry())
    b = _bundle(_FakeService(question_for=slow))
    slot = QuizSlot()
    resp = await handle_quiz(
        MagicMock(command="спроси по географии"), cache=cache, quiz=b, slot=slot,
    )
    assert resp.text == PREMATURE_QUIZ_TEXT
    assert slot.task is not None
    assert slot.subject == "География"
    release.set()
    await slot.task  # эстафетный сигнал уже отдан; дожидаемся фоновой генерации
    assert slot.question == "Готовый вопрос."


@pytest.mark.asyncio
async def test_genitive_subject_matches_command(monkeypatch):
    # «по биологии» (родительный падеж) находит предмет «Биология»
    monkeypatch.setattr("alice_skill.handlers.quiz.DIRECT_TIMEOUT", 0.1)
    cache = _cache(_entry(subject="География"), _entry(subject="Биология"))
    b = _bundle(_FakeService())
    resp = await handle_quiz(
        MagicMock(command="спроси по биологии"), cache=cache, quiz=b, slot=QuizSlot(),
    )
    assert resp.text == QUIZ_FAIL_TEXT  # предмет найден, fake-вопрос не генерируется

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_quiz_handlers.py -q`
Expected: FAIL (ModuleNotFoundError: handlers.quiz)

- [ ] **Step 3: Implement**

`alice_skill/handlers/quiz.py`:

```python
from __future__ import annotations

import asyncio
import logging

from aliceio import F, Router
from aliceio.types import Message, Response

from quiz_library.model import HomeworkEntry
from quiz_library.parser import parse_paragraph

from alice_skill.quiz_state import QuizSlot
from alice_skill.quiz_service import QuizBundle

logger = logging.getLogger(__name__)

quiz_router = Router(name="quiz")

QUIZ_FILTER = F.command.contains("спроси") | F.command.contains("проверь")

DIRECT_TIMEOUT = 3.5

QUIZ_NOT_CONFIGURED_TEXT = "Викторина не настроена. Попроси взрослых включить её."
NO_HOMEWORK_TEXT = "Сегодня по {subject} ничего не задано."
ASK_SUBJECT_TEXT = "По какому предмету спросить?"
NO_PARAGRAPH_TEXT = "Не нашла параграф в задании по {subject}. Скажи, например, «параграф 6»."
PREMATURE_QUIZ_TEXT = "Секунду, придумываю вопрос. Скажи «дальше»."
PREMATURE_MORE_TEXT = "Ещё чуть-чуть, придумываю вопрос. Скажи «дальше» ещё раз."
QUIZ_FAIL_TEXT = "Не получилось придумать вопрос. Попробуй ещё раз."


def _quiz_task(service, entry: HomeworkEntry, slot: QuizSlot):
    async def run() -> None:
        try:
            q = await service.question_for(entry)
        except Exception:
            logger.exception("quiz generation failed")
            q = None
        slot.finish(entry.subject, q.text if q else None)

    return asyncio.create_task(run())


def _resolve_subject(command: str, entries: list[HomeworkEntry], names: list[str]) -> str | None:
    # команда «спроси по биологии» — родительный падеж: «биология» напрямую
    # как подстрока не встретится, поэтому сравниваем и по основе без последней буквы
    command_low = command.lower()
    for name in names:
        name_low = name.lower()
        if name_low in command_low or name_low[:-1] in command_low:
            return name
    distinct = {e.subject for e in entries}
    if len(distinct) == 1:
        return distinct.pop()
    return None


def _entry_for(entries: list[HomeworkEntry], subject: str) -> HomeworkEntry | None:
    for e in entries:
        if e.subject.lower() == subject.lower():
            return e
    return None


@quiz_router.message(QUIZ_FILTER)
async def handle_quiz(message: Message, cache, quiz: QuizBundle | None, slot: QuizSlot | None) -> Response:
    if quiz is None or slot is None:
        return Response(text=QUIZ_NOT_CONFIGURED_TEXT)
    service = quiz.service()
    if service is None:
        return Response(text=QUIZ_NOT_CONFIGURED_TEXT)

    result = cache.get()
    entries = list(result.entries) if result is not None else []

    subject = _resolve_subject(message.command, entries, quiz.subject_names)
    if subject is None:
        if not entries:
            return Response(text=NO_HOMEWORK_TEXT.format(subject="этим предметам"))
        return Response(text=ASK_SUBJECT_TEXT)

    entry = _entry_for(entries, subject)
    if entry is None:
        return Response(text=NO_HOMEWORK_TEXT.format(subject=subject.lower()))

    patterns = service.patterns_for(subject)
    number = parse_paragraph(entry.content, patterns) if patterns else None
    if number is None:
        return Response(text=NO_PARAGRAPH_TEXT.format(subject=subject.lower()))

    if slot.question is not None and slot.subject is not None and slot.subject.lower() == subject.lower():
        text = slot.question
        slot.clear()
        return Response(text=text)

    if (
        slot.task is not None
        and not slot.task.done()
        and slot.subject is not None
        and slot.subject.lower() == subject.lower()
        and slot.paragraph == number
    ):
        return Response(text=PREMATURE_QUIZ_TEXT)

    task = _quiz_task(service, entry, slot)
    slot.set_pending(subject=subject, paragraph=number, task=task)

    done, _ = await asyncio.wait({task}, timeout=DIRECT_TIMEOUT)
    if task in done:
        if slot.question is not None:
            text = slot.question
            slot.clear()
            return Response(text=text)
        slot.clear()
        return Response(text=QUIZ_FAIL_TEXT)
    return Response(text=PREMATURE_QUIZ_TEXT)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_quiz_handlers.py -q`
Expected: PASS (10 passed)

- [ ] **Step 5: Commit**

```bash
git add alice_skill/handlers/quiz.py tests/test_quiz_handlers.py
git commit -m "feat: quiz router with try-direct and premature fallback"
```

---

### Task 6: «дальше» отдаёт вопрос квиза (приоритет слота)

**Files:**
- Modify: `alice_skill/handlers/more.py`
- Test: `tests/test_handlers.py`

**Interfaces:**
- Consumes: `QuizSlot` (Task 3), константы `PREMATURE_MORE_TEXT`, `QUIZ_FAIL_TEXT` из `handlers/quiz.py` (Task 5).
- Produces: `handle_more(message, cache, slot: QuizSlot | None = None) -> Response`.

Логика спеки §7: (1) `slot` есть и `slot.question` не None → вернуть вопрос, `slot.clear()`; (2) `slot.task` не None и не закончен → «Ещё чуть-чуть…»; (3) `slot.task` не None и закончен (вопрос так и не появился) → `slot.clear()`, «Не получилось…»; (4) иначе прежняя домашка.

- [ ] **Step 1: Write the failing tests**

В `tests/test_handlers.py` добавить (импорты в начало файла: `import asyncio`, `from alice_skill.quiz_state import QuizSlot`):

```python
@pytest.mark.asyncio
async def test_more_serves_quiz_question_first():
    cache = _fake_cache(_ok_result("домашний текст"))
    slot = QuizSlot()
    slot.subject = "География"
    slot.question = "Вопрос квиза."
    result = await handle_more(_fake_message("дальше"), cache=cache, slot=slot)
    assert result.text == "Вопрос квиза."
    assert slot.has_pending is False


@pytest.mark.asyncio
async def test_more_falls_back_to_homework_without_slot():
    cache = _fake_cache(_ok_result("домашний текст"))
    result = await handle_more(_fake_message("дальше"), cache=cache)
    assert result.text == "домашний текст"


@pytest.mark.asyncio
async def test_more_still_waiting_while_generation_running():
    cache = _fake_cache(_ok_result("домашний текст"))
    slot = QuizSlot()
    slot.task = asyncio.create_task(asyncio.sleep(60))
    result = await handle_more(_fake_message("дальше"), cache=cache, slot=slot)
    assert "чуть-чуть" in result.text.lower()


@pytest.mark.asyncio
async def test_more_fail_when_generation_finished_without_question():
    cache = _fake_cache(_ok_result("домашний текст"))
    slot = QuizSlot()
    task = asyncio.create_task(asyncio.sleep(0))
    await task
    slot.task = task  # done(), question None
    result = await handle_more(_fake_message("дальше"), cache=cache, slot=slot)
    assert slot.has_pending is False
    assert "не получилось" in result.text.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_handlers.py -q`
Expected: FAIL (handle_more не принимает slot; quiz-проверок нет)

- [ ] **Step 3: Implement**

`alice_skill/handlers/more.py`:

```python
from aliceio import F, Router
from aliceio.types import Message, Response

from alice_skill.quiz_state import QuizSlot

from .common import HINT_TEXT
from .quiz import PREMATURE_MORE_TEXT, QUIZ_FAIL_TEXT

more_router = Router(name="more")


@more_router.message(F.command == "дальше")
async def handle_more(message: Message, cache, slot: QuizSlot | None = None) -> Response:
    if slot is not None:
        if slot.question is not None:
            text = slot.question
            slot.clear()
            return Response(text=text)
        if slot.task is not None:
            if slot.task.done():
                slot.clear()
                return Response(text=QUIZ_FAIL_TEXT)
            return Response(text=PREMATURE_MORE_TEXT)
    result = cache.get()
    if result is not None:
        return Response(text=result.text)
    return Response(text=HINT_TEXT)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_handlers.py -q`
Expected: PASS (все старые + 4 новых)

- [ ] **Step 5: Commit**

```bash
git add alice_skill/handlers/more.py tests/test_handlers.py
git commit -m "feat: more handler serves pending quiz question first"
```

---

### Task 7: Сборка приложения и зависимость

**Files:**
- Modify: `alice_skill/skill.py`
- Modify: `requirements.txt`
- Test: `tests/test_skill.py`

**Interfaces:**
- Consumes: `build_quiz` (Task 4), `QuizSlot` (Task 3), `quiz_router` (Task 5), `more_router`/`handle_more` (Task 6).
- Produces: `create_app(config)`:
  - `bundle = build_quiz(config)`; `slot = QuizSlot()`;
  - `Dispatcher(..., quiz=bundle, slot=slot)`;
  - порядок роутеров: start → homework → **quiz** → more → fallback;
  - `@dp.shutdown()` также `await bundle.close()`, если bundle не None.
  - `requirements.txt` получает `quiz-library @ git+...`.

- [ ] **Step 1: Write the failing tests**

В `tests/test_skill.py` добавить:

```python
from alice_skill.handlers.quiz import QUIZ_NOT_CONFIGURED_TEXT


@pytest.mark.asyncio
async def test_quiz_command_not_configured():
    cache = HomeworkCache()
    worker = MagicMock(spec=PrefetchWorker)
    app, dp = _free_app(_make_config, cache=cache, worker=worker)
    skill = Skill(skill_id="test-skill")
    update = _make_update("спроси по географии")
    resp = await dp.feed_webhook_update(skill, update)
    assert resp is not None
    assert resp.response.text == QUIZ_NOT_CONFIGURED_TEXT


@pytest.mark.asyncio
async def test_router_order_quiz_before_fallback_but_after_homework():
    # «проверь по географии» не должен уходить в fallback даже без квиза
    cache = HomeworkCache()
    worker = MagicMock(spec=PrefetchWorker)
    app, dp = _free_app(_make_config, cache=cache, worker=worker)
    skill = Skill(skill_id="test-skill")
    update = _make_update("проверь меня по географии")
    resp = await dp.feed_webhook_update(skill, update)
    assert resp is not None
    assert resp.response.text == QUIZ_NOT_CONFIGURED_TEXT
```

Примечание: `_make_config` (без llm) → `quiz=None`; `_free_app` инжектирует cache/worker; quiz/slot подставляются в `workflow_data` самим `create_app`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_skill.py -q`
Expected: FAIL (quiz-команда уходит в fallback)

- [ ] **Step 3: Implement**

`alice_skill/skill.py` — правки:

```python
from alice_skill.handlers.more import more_router
from alice_skill.handlers.quiz import quiz_router
from alice_skill.quiz_service import build_quiz
from alice_skill.quiz_state import QuizSlot
```

в `create_app`:

```python
    quiz = build_quiz(config)
    slot = QuizSlot()

    dp = Dispatcher(
        response_timeout=4.0,
        cache=cache,
        worker=worker,
        quiz=quiz,
        slot=slot,
    )

    # Router order matters: start → homework → quiz → more → fallback
    dp.include_router(start_router)
    dp.include_router(homework_router)
    dp.include_router(quiz_router)
    dp.include_router(more_router)
    dp.include_router(fallback_router)
```

в shutdown-хендлере:

```python
    @dp.shutdown()
    async def on_shutdown() -> None:
        logger.info("stopping prefetch worker")
        await worker.stop()
        if quiz is not None:
            await quiz.close()
```

`requirements.txt` — добавить строку (в секцию с внешними git-зависимостями, рядом с netschoolapi-plus):

```
quiz-library @ git+https://github.com/freeuser3/quiz-library.git
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_skill.py -q`
Expected: PASS (все старые + 2 новых)

- [ ] **Step 5: Commit**

```bash
git add alice_skill/skill.py requirements.txt tests/test_skill.py
git commit -m "feat: wire quiz router, bundle and slot into app"
```

---

### Task 8: Полный прогон

- [ ] **Step 1: Установить зависимости**

Run: `pip install -r requirements.txt` (подтянет quiz-library), затем
Run: `python -m pytest -q`
Expected: весь набор зелёный (включая новые `test_config/test_homework/test_sgo/test_quiz_state/test_quiz_service/test_quiz_handlers/test_handlers/test_skill`).

- [ ] **Step 2: Проверка review-focus вручную (без сети)**

Смоук-скрипт поверх Dispatcher не требуется: review-focus покрыт тестами Tasks 5-7. Достаточно убедиться, что без `config.json` (llm отсутствует) навык стартует: 
Run: `python -c "from alice_skill.config import load_config; from tests.test_skill import _make_config, create_app; from unittest.mock import MagicMock"` — запуск приложения без quiz-конфига не бросает (тест `test_quiz_command_not_configured` уже доказывает это через feed_webhook_update).

- [ ] **Step 3: Итог**

Записать в SDD-ledger репо (`.superpowers/sdd/.../progress.md`): summary задач 1-8, runtime-usage записи, отметки `finish(slot)`/`asyncio.wait` удачно подтверждены тестами. Обновить `docs/` (README: короткая секция «Викторина», конфиг `llm`, триггеры).