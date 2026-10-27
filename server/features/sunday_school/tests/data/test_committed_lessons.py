"""The committed 2026 lesson files (specs/026-sunday-school US5, R-08).

Checks what the migration does not: the exact order, the official dates only, an icon on every
section, and every Bible reference against the real Bible data files, read by path so this
feature never imports the Bible feature (constitution: features never import each other).
"""

import datetime
import json
from pathlib import Path

import pytest

from features.sunday_school.content_validation import scripture_problems
from features.sunday_school.domain.scripture_index import ScriptureIndex
from features.sunday_school.lesson_files import LESSON_DATA_DIR, read_lessons, read_year

BIBLE_DATA_FILES = sorted((Path(__file__).resolve().parents[3] / "bible" / "data").glob("*.json"))
LESSONS = read_lessons(LESSON_DATA_DIR / "2026")

EXPECTED_ORDER = [
    "Josué",
    "Rute",
    "2 Samuel",
    "1 Reis",
    "2 Reis",
    "2 Crônicas",
    "Salmos",
    "Provérbios",
    "Isaías",
    "Ezequiel",
    "Daniel",
    "Profetas Menores II",
    "Profetas Menores III",
    "Profetas Menores IV",
    "Período Intertestamentário",
    "Ato 4",
    "Mateus",
    "Marcos",
]

# The dates marked "oficial" in the source list; inferred dates never go in.
OFFICIAL_DATES = {
    "2 Samuel": datetime.date(2026, 5, 17),
    "1 Reis": datetime.date(2026, 5, 24),
    "2 Reis": datetime.date(2026, 5, 31),
    "2 Crônicas": datetime.date(2026, 6, 14),
    "Salmos": datetime.date(2026, 7, 5),
    "Provérbios": datetime.date(2026, 7, 12),
    "Isaías": datetime.date(2026, 7, 26),
    "Ezequiel": datetime.date(2026, 8, 9),
    "Daniel": datetime.date(2026, 8, 16),
}


def _scripture_from_files(paths: list[Path]) -> ScriptureIndex:
    """Minimum verse count per chapter across the translations, and the first one's names."""
    counts: dict[str, list[int]] = {}
    names: dict[str, str] = {}
    for path in paths:
        for book in json.loads(path.read_text(encoding="utf-8-sig")):
            verses = [len(chapter) for chapter in book["chapters"]]
            known = counts.setdefault(book["abbrev"], verses)
            counts[book["abbrev"]] = [min(a, b) for a, b in zip(known, verses)]
            names.setdefault(book["abbrev"], book["name"])
    return ScriptureIndex(counts, names)


SCRIPTURE = _scripture_from_files(BIBLE_DATA_FILES)


def test_year_and_theme() -> None:
    year = read_year(LESSON_DATA_DIR / "2026")

    assert (year.year, year.theme) == (2026, "O Drama das Escrituras")


def test_eighteen_lessons_in_bible_order() -> None:
    assert len(LESSONS) == 18
    for lesson, expected in zip(LESSONS, EXPECTED_ORDER):
        assert expected in lesson.title


def test_only_official_dates() -> None:
    dates = {
        name: lesson.date
        for lesson, name in zip(LESSONS, EXPECTED_ORDER)
        if lesson.date is not None
    }

    assert dates == OFFICIAL_DATES


def test_every_section_has_an_icon() -> None:
    missing = [
        (lesson.title, section.title)
        for lesson in LESSONS
        for section in lesson.content.sections
        if section.icon is None
    ]

    assert missing == []


@pytest.mark.parametrize("lesson", LESSONS, ids=[lesson.title for lesson in LESSONS])
def test_every_reference_exists_in_every_translation(lesson: object) -> None:
    assert len(BIBLE_DATA_FILES) >= 2
    assert scripture_problems(lesson.content, SCRIPTURE) == []  # type: ignore[attr-defined]
