"""Public reading of Sunday school lessons (specs/026-sunday-school US1)."""

from core.domain.exceptions import SundaySchoolLessonNotFoundError, SundaySchoolYearNotFoundError
from features.sunday_school.domain.lesson_status import LessonStatus
from features.sunday_school.domain.scripture_index import ScriptureIndex
from features.sunday_school.dtos import LessonDTO, SundaySchoolIndexDTO, YearDTO
from features.sunday_school.repositories.interfaces import (
    SundaySchoolLessonRepository,
    SundaySchoolYearRepository,
)
from features.sunday_school.services.lesson_books import with_books


class SundaySchoolReadingService:
    """Only published lessons, and years that have one, ever leave this service.

    >>> service.index(None).default_year
    2026
    """

    def __init__(
        self,
        year_repository: SundaySchoolYearRepository,
        lesson_repository: SundaySchoolLessonRepository,
        scripture: ScriptureIndex,
    ) -> None:
        self._years = year_repository
        self._lessons = lesson_repository
        self._scripture = scripture

    def index(self, year: int | None) -> SundaySchoolIndexDTO:
        """The published years, the default (newest of them) and the lessons of ``year`` — the
        default when None. Raises ``SundaySchoolYearNotFoundError`` for a year not published."""
        years = self._years.published_years()
        default = years[0].year if years else None
        chosen = self._chosen_year(years, default if year is None else year)
        lessons = self._lessons.published_summaries(chosen.year) if chosen else []
        return SundaySchoolIndexDTO(years=years, default_year=default, year=chosen, lessons=lessons)

    def lesson(self, lesson_id: int) -> LessonDTO:
        record = self._lessons.get(lesson_id)
        if record is None or record.status is not LessonStatus.PUBLISHED:
            raise SundaySchoolLessonNotFoundError(lesson_id)
        return with_books(record, self._scripture)

    @staticmethod
    def _chosen_year(years: list[YearDTO], year: int | None) -> YearDTO | None:
        if year is None:
            return None
        for candidate in years:
            if candidate.year == year:
                return candidate
        raise SundaySchoolYearNotFoundError(year)
