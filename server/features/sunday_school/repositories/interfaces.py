"""Ports of Sunday school persistence (specs/026-sunday-school). The ORM stays behind them."""

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from features.sunday_school.dtos import (
    LessonFieldsDTO,
    LessonRecordDTO,
    LessonSummaryDTO,
    YearAdminDTO,
    YearDTO,
)


class SundaySchoolYearRepository(Protocol):
    def published_years(self) -> list[YearDTO]:
        """Years with at least one published lesson, newest first."""
        ...

    def all_years(self) -> list[YearAdminDTO]:
        """Every year row with its lesson counts, newest first."""
        ...

    def get(self, year: int) -> YearDTO | None: ...

    def set_theme(self, year: int, theme: str) -> YearAdminDTO | None:
        """None when the year has no row."""
        ...


class SundaySchoolLessonRepository(Protocol):
    def published_summaries(self, year: int) -> list[LessonSummaryDTO]:
        """Published lessons of ``year``, by position."""
        ...

    def lessons_of_year(self, year: int) -> list[LessonRecordDTO]:
        """Every lesson of ``year``, drafts included, by position."""
        ...

    def get(self, lesson_id: int) -> LessonRecordDTO | None: ...

    def create(self, fields: LessonFieldsDTO, author_id: UUID) -> LessonRecordDTO:
        """Create the year row if missing and append the lesson to the end of its year."""
        ...

    def update(self, lesson_id: int, fields: LessonFieldsDTO, author_id: UUID) -> LessonRecordDTO:
        """Overwrite the fields; a new year appends it there and renumbers the year it left."""
        ...

    def delete(self, lesson_id: int) -> None:
        """Delete and renumber its year."""
        ...

    def ids_of_year(self, year: int) -> list[int] | None:
        """Lesson ids of ``year`` in order; None when the year has no row."""
        ...

    def set_order(self, year: int, lesson_ids: Sequence[int]) -> None:
        """Positions ``0..n-1`` following ``lesson_ids``."""
        ...
