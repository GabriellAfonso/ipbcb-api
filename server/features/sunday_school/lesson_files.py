"""Reads the frozen lesson files the initial-load migration stores (specs/026-sunday-school R-08).

One directory per year: ``year.json`` (``year``, ``theme``) and one ``NN-<slug>.json`` per lesson
(``title``, ``date``, ``content``), ``NN`` giving the order. The content goes through the same
schema as API writes; Bible references are checked by the committed-files test, not here.
"""

import datetime
import json
from pathlib import Path

from core.application.dtos.strict_base import StrictBaseModel
from features.sunday_school.content_schema import LessonContent

LESSON_DATA_DIR = Path(__file__).parent / "migrations" / "data"


class YearFileDTO(StrictBaseModel):
    year: int
    theme: str


class LessonFileDTO(StrictBaseModel):
    """One lesson as stored on disk.

    >>> LessonFileDTO.model_validate_json(Path("01-josue.json").read_text(encoding="utf-8"))
    """

    title: str
    date: datetime.date | None
    content: LessonContent


def read_year(directory: Path) -> YearFileDTO:
    return YearFileDTO.model_validate(_json(directory / "year.json"))


def read_lessons(directory: Path) -> list[LessonFileDTO]:
    """Every lesson file of ``directory``, in file-name order.

    >>> [lesson.title for lesson in read_lessons(LESSON_DATA_DIR / "2026")][:2]
    ['Josué e a conquista da terra', 'O Resgate na História da Redenção — O Livro de Rute']
    """
    paths = sorted(path for path in directory.glob("*.json") if path.name != "year.json")
    return [LessonFileDTO.model_validate(_json(path)) for path in paths]


def _json(path: Path) -> dict[str, object]:
    loaded: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    return loaded
