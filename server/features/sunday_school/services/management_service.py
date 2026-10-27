"""Panel use cases of Sunday school lessons and years (specs/026-sunday-school US2–US4)."""

from collections.abc import Mapping
from uuid import UUID

from core.domain.exceptions import (
    SundaySchoolLessonNotFoundError,
    SundaySchoolOrderMismatchError,
    SundaySchoolYearNotFoundError,
)
from features.sunday_school.content_validation import validate_content
from features.sunday_school.domain.scripture_index import ScriptureIndex
from features.sunday_school.dtos import (
    LessonCreateDTO,
    LessonDTO,
    LessonFieldsDTO,
    LessonOrderDTO,
    LessonPatchDTO,
    LessonRecordDTO,
    YearAdminDTO,
)
from features.sunday_school.repositories.interfaces import (
    SundaySchoolLessonRepository,
    SundaySchoolYearRepository,
)
from features.sunday_school.services.lesson_books import with_books


def _fields_of(record: LessonRecordDTO) -> LessonFieldsDTO:
    return LessonFieldsDTO(
        year=record.year.year,
        title=record.title,
        date=record.date,
        teacher=record.teacher,
        status=record.status,
        content=record.content,
    )


class SundaySchoolManagementService:
    """Writes come with the author's id; the content is validated on every write.

    >>> service.create(LessonCreateDTO(year=2026, title="Panorama de Gênesis",
    ...     status="draft", content=content), author_id)
    LessonDTO(id=19, position=18, ...)
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

    def lessons_of_year(self, year: int) -> list[LessonDTO]:
        return [self._served(record) for record in self._lessons.lessons_of_year(year)]

    def lesson(self, lesson_id: int) -> LessonDTO:
        return self._served(self._existing(lesson_id))

    def create(self, dto: LessonCreateDTO, author_id: UUID) -> LessonDTO:
        fields = LessonFieldsDTO(
            **dto.model_dump(exclude={"content"}), content=self._valid(dto.content)
        )
        return self._served(self._lessons.create(fields, author_id))

    def update(self, lesson_id: int, patch: LessonPatchDTO, author_id: UUID) -> LessonDTO:
        """Only the fields sent change; a new ``year`` moves the lesson to that year's end."""
        current = _fields_of(self._existing(lesson_id))
        changes = {name: getattr(patch, name) for name in patch.model_fields_set}
        if "content" in changes:
            changes["content"] = self._valid(patch.content or {})
        fields = current.model_copy(update=changes)
        return self._served(self._lessons.update(lesson_id, fields, author_id))

    def delete(self, lesson_id: int) -> None:
        self._existing(lesson_id)
        self._lessons.delete(lesson_id)

    def set_order(self, dto: LessonOrderDTO) -> None:
        """The list must be exactly the year's lessons (drafts included), each once."""
        expected = self._lessons.ids_of_year(dto.year)
        if expected is None:
            raise SundaySchoolYearNotFoundError(dto.year)
        if sorted(dto.lesson_ids) != sorted(expected):
            raise SundaySchoolOrderMismatchError(dto.year, expected, dto.lesson_ids)
        self._lessons.set_order(dto.year, dto.lesson_ids)

    def years(self) -> list[YearAdminDTO]:
        return self._years.all_years()

    def set_theme(self, year: int, theme: str) -> YearAdminDTO:
        updated = self._years.set_theme(year, theme)
        if updated is None:
            raise SundaySchoolYearNotFoundError(year)
        return updated

    def _valid(self, raw: Mapping[str, object]) -> dict[str, object]:
        return validate_content(raw, self._scripture).model_dump(mode="json")

    def _existing(self, lesson_id: int) -> LessonRecordDTO:
        record = self._lessons.get(lesson_id)
        if record is None:
            raise SundaySchoolLessonNotFoundError(lesson_id)
        return record

    def _served(self, record: LessonRecordDTO) -> LessonDTO:
        return with_books(record, self._scripture)
