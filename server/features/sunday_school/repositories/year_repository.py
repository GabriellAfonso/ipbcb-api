"""ORM persistence of Sunday school years (specs/026-sunday-school data-model)."""

from django.db.models import Count, Q, QuerySet

from features.sunday_school.domain.lesson_status import LessonStatus
from features.sunday_school.dtos import YearAdminDTO, YearDTO
from features.sunday_school.models import SundaySchoolYear

_PUBLISHED = Q(lessons__status=LessonStatus.PUBLISHED.value)


def _with_counts() -> QuerySet[SundaySchoolYear]:
    return SundaySchoolYear.objects.annotate(
        lesson_count=Count("lessons"), published_count=Count("lessons", filter=_PUBLISHED)
    )


def _admin_dto(row: SundaySchoolYear) -> YearAdminDTO:
    return YearAdminDTO(
        year=row.year,
        theme=row.theme,
        lesson_count=getattr(row, "lesson_count"),
        published_count=getattr(row, "published_count"),
    )


class SundaySchoolYearRepositoryImpl:
    """ORM implementation of ``SundaySchoolYearRepository``.

    >>> SundaySchoolYearRepositoryImpl().published_years()
    [YearDTO(year=2026, theme='O Drama das Escrituras')]
    """

    def published_years(self) -> list[YearDTO]:
        rows = SundaySchoolYear.objects.filter(_PUBLISHED).distinct().order_by("-year")
        return [YearDTO(year=row.year, theme=row.theme) for row in rows]

    def all_years(self) -> list[YearAdminDTO]:
        return [_admin_dto(row) for row in _with_counts().order_by("-year")]

    def get(self, year: int) -> YearDTO | None:
        row = SundaySchoolYear.objects.filter(year=year).first()
        return YearDTO(year=row.year, theme=row.theme) if row else None

    def set_theme(self, year: int, theme: str) -> YearAdminDTO | None:
        row = SundaySchoolYear.objects.filter(year=year).first()
        if row is None:
            return None
        row.theme = theme
        row.save(update_fields=["theme", "updated_at"])
        return _admin_dto(_with_counts().get(pk=row.pk))
