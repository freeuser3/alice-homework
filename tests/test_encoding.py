from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SOURCE_SUBDIRS = ("alice_skill", "tests")
TEXT_FILES = ("README.md", "config.example.json")
EXPECTED_RUSSIAN = {
    "README.md": ("Скажи домашку", "СГО"),
}


def _collect_source_files() -> list:
    files = []
    for subdir in SOURCE_SUBDIRS:
        base = PROJECT_ROOT / subdir
        if base.exists():
            files.extend(sorted(base.rglob("*.py")))
    return files


SOURCE_FILES = _collect_source_files()


@pytest.mark.parametrize(
    "path",
    SOURCE_FILES,
    ids=lambda p: p.relative_to(PROJECT_ROOT).as_posix(),
)
def test_python_source_is_valid_utf8_roundtrip(path):
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    assert text.encode("utf-8") == raw


@pytest.mark.parametrize("filename", TEXT_FILES)
def test_text_file_is_valid_utf8_roundtrip(filename):
    raw = (PROJECT_ROOT / filename).read_bytes()
    raw.decode("utf-8")
    assert raw.decode("utf-8").encode("utf-8") == raw


@pytest.mark.parametrize("filename,phrases", EXPECTED_RUSSIAN.items())
def test_expected_russian_phrases_are_intact(filename, phrases):
    text = (PROJECT_ROOT / filename).read_text(encoding="utf-8")
    for phrase in phrases:
        assert phrase in text