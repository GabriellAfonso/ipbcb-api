"""ORM persistence of Sunday school lessons (specs/026-sunday-school data-model, R-07).

Positions stay dense (0..n-1 per year): every write that removes a lesson from a year renumbers
what is left, in the same transaction.
"""

from collections.abc import Sequence
from uuid import UUID

from django.db import transaction
from django.db.models import Max, QuerySet

from features.sunday_school.domain.lesson_status import LessonStatus
from features.sunday_school.dtos import (
    LessonFieldsDTO,
    LessonRecordDTO,
    LessonSummaryDTO,
    YearDTO,
)
from features.sunday_school.models import SundaySchoolLesson, SundaySchoolYear

_ORDER = ("position", "id")


def _of_year(year: int) -> QuerySet[SundaySchoolLesson]:
    return SundaySchoolLesson.objects.filter(year__year=year).order_by(*_ORDER)


def _summary(row: SundaySchoolLesson) -> LessonSummaryDTO:
    return LessonSummaryDTO(
        id=row.pk, title=row.title, date=row.date, teacher=row.teacher, position=row.position
    )


def _record(row: SundaySchoolLesson) -> LessonRecordDTO:
    return LessonRecordDTO(
        **_summary(row).model_dump(),
        status=LessonStatus(row.status),
        year=YearDTO(year=row.year.year, theme=row.year.theme),
        content=row.content,
    )


def _locked_year(year: int) -> SundaySchoolYear:
    """The year row, created if missing, locked so two appends cannot take the same position."""
    row, _ = SundaySchoolYear.objects.get_or_create(year=year)
    return SundaySchoolYear.objects.select_for_update().get(pk=row.pk)


def _next_position(year: SundaySchoolYear) -> int:
    last = SundaySchoolLesson.objects.filter(year=year).aggregate(last=Max("position"))["last"]
    return 0 if last is None else last + 1


def _renumber(year_id: int) -> None:
    rows = list(SundaySchoolLesson.objects.filter(year_id=year_id).order_by(*_ORDER))
    for index, row in enumerate(rows):
        row.position = index
    SundaySchoolLesson.objects.bulk_update(rows, ["position"])


def _assign(row: SundaySchoolLesson, fields: LessonFieldsDTO, author_id: UUID) -> None:
    row.title = fields.title
    row.date = fields.date
    row.teacher = fields.teacher
    row.status = fields.status.value
    row.content = fields.content
    row.updated_by_id = author_id


class SundaySchoolLessonRepositoryImpl:
    """ORM implementation of ``SundaySchoolLessonRepository``.

    >>> SundaySchoolLessonRepositoryImpl().ids_of_year(2026)
    [1, 2, 3]
    """

    def published_summaries(self, year: int) -> list[LessonSummaryDTO]:
        rows = _of_year(year).filter(status=LessonStatus.PUBLISHED.value)
        return [_summary(row) for row in rows]

    def lessons_of_year(self, year: int) -> list[LessonRecordDTO]:
        return [_record(row) for row in _of_year(year).select_related("year")]

    def get(self, lesson_id: int) -> LessonRecordDTO | None:
        row = SundaySchoolLesson.objects.select_related("year").filter(pk=lesson_id).first()
        return _record(row) if row else None

    def create(self, fields: LessonFieldsDTO, author_id: UUID) -> LessonRecordDTO:
        with transaction.atomic():
            year = _locked_year(fields.year)
            row = SundaySchoolLesson(
                year=year, position=_next_position(year), created_by_id=author_id
            )
            _assign(row, fields, author_id)
            row.save()
        return _record(row)

    def update(self, lesson_id: int, fields: LessonFieldsDTO, author_id: UUID) -> LessonRecordDTO:
        with transaction.atomic():
            row = SundaySchoolLesson.objects.select_related("year").get(pk=lesson_id)
            left_year_id = row.year_id
            if row.year.year != fields.year:
                row.year = _locked_year(fields.year)
                row.position = _next_position(row.year)
            _assign(row, fields, author_id)
            row.save()
            if row.year_id != left_year_id:
                _renumber(left_year_id)
        return _record(row)

    def delete(self, lesson_id: int) -> None:
        with transaction.atomic():
            row = SundaySchoolLesson.objects.filter(pk=lesson_id).first()
            if row is None:
                return
            row.delete()
            _renumber(row.year_id)

    def ids_of_year(self, year: int) -> list[int] | None:
        if not SundaySchoolYear.objects.filter(year=year).exists():
            return None
        return list(_of_year(year).values_list("id", flat=True))

    def set_order(self, year: int, lesson_ids: Sequence[int]) -> None:
        position_of = {lesson_id: index for index, lesson_id in enumerate(lesson_ids)}
        with transaction.atomic():
            rows = list(_of_year(year).select_for_update())
            for row in rows:
                row.position = position_of[row.pk]
            SundaySchoolLesson.objects.bulk_update(rows, ["position"])
