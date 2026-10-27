"""DTOs of Sunday school years and lessons (specs/026-sunday-school data-model).

``content`` arrives as a raw JSON object and is validated by ``content_validation`` in the
service, so a content mistake answers ``SUNDAY_SCHOOL_CONTENT_INVALID`` with its path rather than
the generic ``VALIDATION_ERROR`` the rest of the body gives.
"""

import datetime
from typing import Annotated

from pydantic import AfterValidator, Field, model_validator

from core.application.dtos.strict_base import StrictBaseModel
from features.sunday_school.domain.lesson_status import LessonStatus

MIN_YEAR = 2000
MAX_YEAR = 2100
MAX_LESSONS_PER_ORDER = 500

YearNumber = Annotated[int, Field(ge=MIN_YEAR, le=MAX_YEAR)]


def _require_non_blank(value: str) -> str:
    if not value.strip():
        raise ValueError(f"o título não pode ficar em branco; recebido {value!r}")
    return value


Title = Annotated[str, Field(max_length=200), AfterValidator(_require_non_blank)]
Teacher = Annotated[str, Field(max_length=120)]
Theme = Annotated[str, Field(max_length=200)]
RawContent = dict[str, object]


class YearDTO(StrictBaseModel):
    year: int
    theme: str


class YearAdminDTO(YearDTO):
    """A year as the panel lists it, with how many lessons it holds."""

    lesson_count: int
    published_count: int


class LessonSummaryDTO(StrictBaseModel):
    id: int
    title: str
    date: datetime.date | None
    teacher: str
    position: int


class LessonRecordDTO(LessonSummaryDTO):
    """A lesson as stored."""

    status: LessonStatus
    year: YearDTO
    content: RawContent


class BookFactsDTO(StrictBaseModel):
    """Derived from the Bible for a ``book_facts`` card (research R-03).

    >>> BookFactsDTO(name="Marcos", position=41, chapters=16, verses=678)
    """

    name: str
    position: int
    chapters: int
    verses: int


class LessonDTO(LessonRecordDTO):
    """A lesson as served: the stored one plus the facts of the books its cards name."""

    books: dict[str, BookFactsDTO]


class SundaySchoolIndexDTO(StrictBaseModel):
    """``GET api/sunday-school/``: the published years, the default one, and one year's lessons.

    >>> SundaySchoolIndexDTO(years=[], default_year=None, year=None, lessons=[])
    """

    years: list[YearDTO]
    default_year: int | None
    year: YearDTO | None
    lessons: list[LessonSummaryDTO]


class YearQueryDTO(StrictBaseModel):
    """``?year=2026``; absent means the default year."""

    year: YearNumber | None = None


class LessonFieldsDTO(StrictBaseModel):
    """Every stored field of a lesson but its position and authors; ``content`` validated."""

    year: int
    title: str
    date: datetime.date | None
    teacher: str
    status: LessonStatus
    content: RawContent


class LessonCreateDTO(StrictBaseModel):
    """``POST api/sunday-school/manage/lessons/``.

    >>> LessonCreateDTO(year=2026, title="Panorama de Gênesis", status="draft", content={})
    """

    year: YearNumber
    title: Title
    date: datetime.date | None = None
    teacher: Teacher = ""
    status: LessonStatus
    content: RawContent


class LessonPatchDTO(StrictBaseModel):
    """``PATCH api/sunday-school/manage/lessons/{id}/``. Only the fields sent are applied; only
    ``date`` can be cleared with null.

    >>> LessonPatchDTO(status="published").model_fields_set
    {'status'}
    """

    year: YearNumber | None = None
    title: Title | None = None
    date: datetime.date | None = None
    teacher: Teacher | None = None
    status: LessonStatus | None = None
    content: RawContent | None = None

    @model_validator(mode="after")
    def _refuse_clearing_required(self) -> "LessonPatchDTO":
        for name in ("year", "title", "teacher", "status", "content"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} não pode ser nulo; omita o campo para mantê-lo")
        return self


class LessonOrderDTO(StrictBaseModel):
    """``PUT api/sunday-school/manage/lessons/order/``: the year's lessons, first to last."""

    year: YearNumber
    lesson_ids: Annotated[list[int], Field(max_length=MAX_LESSONS_PER_ORDER)]


class YearThemeDTO(StrictBaseModel):
    """``PATCH api/sunday-school/manage/years/{year}/``; blank clears the theme."""

    theme: Theme
