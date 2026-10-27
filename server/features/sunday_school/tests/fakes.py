"""Named in-memory fakes and sample documents for the Sunday school ports (CLAUDE.md §10)."""

from collections.abc import Sequence
from itertools import count
from uuid import UUID

from features.sunday_school.domain.lesson_status import LessonStatus
from features.sunday_school.domain.scripture_index import ScriptureIndex
from features.sunday_school.dtos import (
    LessonFieldsDTO,
    LessonRecordDTO,
    LessonSummaryDTO,
    YearAdminDTO,
    YearDTO,
)

# A small Bible for unit tests: Daniel has 12 chapters, but only three are listed here.
SMALL_SCRIPTURE = ScriptureIndex(
    {"Gn": [31, 25], "Dn": [21, 49, 30], "Mc": [45, 28]},
    {"Gn": "Gênesis", "Dn": "Daniel", "Mc": "Marcos"},
)


def sample_content(**paragraph: object) -> dict[str, object]:
    """One section with one paragraph; keyword arguments override the paragraph's fields.

    >>> sample_content(text="Outro texto")["sections"][0]["blocks"][0]["text"]
    'Outro texto'
    """
    block = {"type": "paragraph", "text": "O livro de **Daniel**…", **paragraph}
    return {"sections": [{"title": "Contexto", "icon": "hourglass", "blocks": [block]}]}


def proof(book: str, chapter: int, start: int, end: int | None = None) -> dict[str, object]:
    verses = [{"start": start, "end": end or start}]
    return {
        "printed": f"{book} {chapter}.{start}",
        "reference": {"book": book, "chapter": chapter, "verses": verses},
    }


class FakeYearRepository:
    """Years by number; published flags are read from the lesson fake it shares."""

    def __init__(self, lessons: "FakeLessonRepository") -> None:
        self._lessons = lessons

    def published_years(self) -> list[YearDTO]:
        years = {r.year.year for r in self._lessons.rows.values() if _published(r)}
        return [self._lessons.year(y) for y in sorted(years, reverse=True)]

    def all_years(self) -> list[YearAdminDTO]:
        return [self._admin(year) for year in sorted(self._lessons.themes, reverse=True)]

    def get(self, year: int) -> YearDTO | None:
        return self._lessons.year(year) if year in self._lessons.themes else None

    def set_theme(self, year: int, theme: str) -> YearAdminDTO | None:
        if year not in self._lessons.themes:
            return None
        self._lessons.themes[year] = theme
        return self._admin(year)

    def _admin(self, year: int) -> YearAdminDTO:
        rows = [r for r in self._lessons.rows.values() if r.year.year == year]
        published = sum(1 for r in rows if _published(r))
        return YearAdminDTO(
            **self._lessons.year(year).model_dump(),
            lesson_count=len(rows),
            published_count=published,
        )


class FakeLessonRepository:
    """Lessons by id, with the dense positions the ORM implementation keeps."""

    def __init__(self) -> None:
        self.rows: dict[int, LessonRecordDTO] = {}
        self.themes: dict[int, str] = {}
        self.authors: dict[int, UUID] = {}
        self._ids = count(1)

    def year(self, year: int) -> YearDTO:
        return YearDTO(year=year, theme=self.themes.get(year, ""))

    def published_summaries(self, year: int) -> list[LessonSummaryDTO]:
        return [_summary(r) for r in self._ordered(year) if _published(r)]

    def lessons_of_year(self, year: int) -> list[LessonRecordDTO]:
        return self._ordered(year)

    def get(self, lesson_id: int) -> LessonRecordDTO | None:
        return self.rows.get(lesson_id)

    def create(self, fields: LessonFieldsDTO, author_id: UUID) -> LessonRecordDTO:
        lesson_id = next(self._ids)
        self.themes.setdefault(fields.year, "")
        self._store(lesson_id, fields, len(self._ordered(fields.year)))
        self.authors[lesson_id] = author_id
        return self.rows[lesson_id]

    def update(self, lesson_id: int, fields: LessonFieldsDTO, author_id: UUID) -> LessonRecordDTO:
        old = self.rows[lesson_id]
        self.themes.setdefault(fields.year, "")
        moved = old.year.year != fields.year
        position = len(self._ordered(fields.year)) if moved else old.position
        self._store(lesson_id, fields, position)
        if moved:
            self._renumber(old.year.year)
        self.authors[lesson_id] = author_id
        return self.rows[lesson_id]

    def delete(self, lesson_id: int) -> None:
        year = self.rows.pop(lesson_id).year.year
        self._renumber(year)

    def ids_of_year(self, year: int) -> list[int] | None:
        if year not in self.themes:
            return None
        return [r.id for r in self._ordered(year)]

    def set_order(self, year: int, lesson_ids: Sequence[int]) -> None:
        for position, lesson_id in enumerate(lesson_ids):
            self.rows[lesson_id] = self.rows[lesson_id].model_copy(update={"position": position})

    def _store(self, lesson_id: int, fields: LessonFieldsDTO, position: int) -> None:
        self.rows[lesson_id] = LessonRecordDTO(
            id=lesson_id,
            title=fields.title,
            date=fields.date,
            teacher=fields.teacher,
            position=position,
            status=fields.status,
            year=self.year(fields.year),
            content=fields.content,
        )

    def _ordered(self, year: int) -> list[LessonRecordDTO]:
        rows = [r for r in self.rows.values() if r.year.year == year]
        return sorted(rows, key=lambda r: (r.position, r.id))

    def _renumber(self, year: int) -> None:
        self.set_order(year, [r.id for r in self._ordered(year)])


def _published(record: LessonRecordDTO) -> bool:
    return record.status is LessonStatus.PUBLISHED


def _summary(record: LessonRecordDTO) -> LessonSummaryDTO:
    return LessonSummaryDTO(
        id=record.id,
        title=record.title,
        date=record.date,
        teacher=record.teacher,
        position=record.position,
    )
