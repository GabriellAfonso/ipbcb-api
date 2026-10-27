"""Reading and management services on fakes (specs/026-sunday-school US1–US4)."""

from datetime import date
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError as PydanticValidationError

from core.domain.exceptions import (
    SundaySchoolContentInvalidError,
    SundaySchoolLessonNotFoundError,
    SundaySchoolOrderMismatchError,
    SundaySchoolYearNotFoundError,
)
from features.sunday_school.domain.lesson_status import LessonStatus
from features.sunday_school.dtos import (
    LessonCreateDTO,
    LessonDTO,
    LessonOrderDTO,
    LessonPatchDTO,
)
from features.sunday_school.services.management_service import SundaySchoolManagementService
from features.sunday_school.services.reading_service import SundaySchoolReadingService
from features.sunday_school.tests.fakes import (
    SMALL_SCRIPTURE,
    FakeLessonRepository,
    FakeYearRepository,
    sample_content,
)

AUTHOR = UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture
def lessons() -> FakeLessonRepository:
    return FakeLessonRepository()


@pytest.fixture
def manage(lessons: FakeLessonRepository) -> SundaySchoolManagementService:
    return SundaySchoolManagementService(FakeYearRepository(lessons), lessons, SMALL_SCRIPTURE)


@pytest.fixture
def read(lessons: FakeLessonRepository) -> SundaySchoolReadingService:
    return SundaySchoolReadingService(FakeYearRepository(lessons), lessons, SMALL_SCRIPTURE)


def _create(
    manage: SundaySchoolManagementService,
    year: int = 2026,
    status: LessonStatus = LessonStatus.PUBLISHED,
    title: str = "Panorama",
) -> LessonDTO:
    dto = LessonCreateDTO(year=year, title=title, status=status, content=sample_content())
    return manage.create(dto, AUTHOR)


class TestReading:
    def test_empty_index(self, read: SundaySchoolReadingService) -> None:
        index = read.index(None)

        assert (index.years, index.default_year, index.year, index.lessons) == ([], None, None, [])

    def test_default_is_newest_published_year(
        self, read: SundaySchoolReadingService, manage: SundaySchoolManagementService
    ) -> None:
        _create(manage, 2026)
        _create(manage, 2027, LessonStatus.DRAFT)

        index = read.index(None)

        assert [y.year for y in index.years] == [2026]
        assert index.default_year == 2026
        assert len(index.lessons) == 1

    def test_drafts_never_listed(
        self, read: SundaySchoolReadingService, manage: SundaySchoolManagementService
    ) -> None:
        _create(manage, title="A")
        _create(manage, status=LessonStatus.DRAFT, title="B")

        assert [lesson.title for lesson in read.index(2026).lessons] == ["A"]

    def test_unpublished_year_is_404(
        self, read: SundaySchoolReadingService, manage: SundaySchoolManagementService
    ) -> None:
        _create(manage, 2027, LessonStatus.DRAFT)

        with pytest.raises(SundaySchoolYearNotFoundError):
            read.index(2027)

    def test_draft_lesson_is_404(
        self, read: SundaySchoolReadingService, manage: SundaySchoolManagementService
    ) -> None:
        draft = _create(manage, status=LessonStatus.DRAFT)

        with pytest.raises(SundaySchoolLessonNotFoundError):
            read.lesson(draft.id)
        with pytest.raises(SundaySchoolLessonNotFoundError):
            read.lesson(999)

    def test_lesson_carries_book_facts(
        self, read: SundaySchoolReadingService, manage: SundaySchoolManagementService
    ) -> None:
        content: dict[str, object] = {
            "sections": [{"title": "S", "blocks": [{"type": "book_facts", "book": "Mc"}]}]
        }
        dto = LessonCreateDTO(
            year=2026, title="Marcos", status=LessonStatus.PUBLISHED, content=content
        )
        created = manage.create(dto, AUTHOR)

        books = read.lesson(created.id).books

        assert books["Mc"].model_dump() == {
            "name": "Marcos",
            "position": 3,
            "chapters": 2,
            "verses": 73,
        }


class TestWriting:
    def test_create_appends_and_records_author(
        self, manage: SundaySchoolManagementService, lessons: FakeLessonRepository
    ) -> None:
        first, second = _create(manage), _create(manage)

        assert (first.position, second.position) == (0, 1)
        assert lessons.authors[second.id] == AUTHOR

    def test_create_refuses_bad_content(self, manage: SundaySchoolManagementService) -> None:
        dto = LessonCreateDTO(
            year=2026, title="X", status=LessonStatus.DRAFT, content={"sections": [{"title": "S"}]}
        )
        with pytest.raises(SundaySchoolContentInvalidError):
            manage.create(dto, AUTHOR)

    def test_patch_changes_only_sent_fields(self, manage: SundaySchoolManagementService) -> None:
        lesson = _create(manage, status=LessonStatus.DRAFT)
        other = uuid4()

        updated = manage.update(
            lesson.id, LessonPatchDTO(status=LessonStatus.PUBLISHED, date=date(2026, 8, 16)), other
        )

        assert updated.status is LessonStatus.PUBLISHED
        assert updated.date == date(2026, 8, 16)
        assert updated.title == lesson.title

    def test_patch_to_another_year_moves_to_its_end(
        self, manage: SundaySchoolManagementService
    ) -> None:
        a, b = _create(manage, title="A"), _create(manage, title="B")
        _create(manage, 2027, title="C")

        moved = manage.update(a.id, LessonPatchDTO(year=2027), AUTHOR)

        assert (moved.year.year, moved.position) == (2027, 1)
        assert manage.lesson(b.id).position == 0

    def test_patch_refuses_null_title(self) -> None:
        with pytest.raises(PydanticValidationError):
            LessonPatchDTO.model_validate({"title": None})

    def test_unknown_lesson(self, manage: SundaySchoolManagementService) -> None:
        with pytest.raises(SundaySchoolLessonNotFoundError):
            manage.update(9, LessonPatchDTO(title="X"), AUTHOR)
        with pytest.raises(SundaySchoolLessonNotFoundError):
            manage.delete(9)

    def test_delete_renumbers(self, manage: SundaySchoolManagementService) -> None:
        a, b, c = (_create(manage, title=t) for t in "ABC")

        manage.delete(a.id)

        assert [manage.lesson(x.id).position for x in (b, c)] == [0, 1]


class TestOrderAndYears:
    def test_reorder(self, manage: SundaySchoolManagementService) -> None:
        a, b, c = (_create(manage, title=t) for t in "ABC")

        manage.set_order(LessonOrderDTO(year=2026, lesson_ids=[c.id, a.id, b.id]))

        assert [lesson.title for lesson in manage.lessons_of_year(2026)] == ["C", "A", "B"]

    @pytest.mark.parametrize("ids", [[1], [1, 2, 2], [1, 2, 99]])
    def test_reorder_mismatch(self, manage: SundaySchoolManagementService, ids: list[int]) -> None:
        _create(manage)
        _create(manage)

        with pytest.raises(SundaySchoolOrderMismatchError):
            manage.set_order(LessonOrderDTO(year=2026, lesson_ids=ids))

    def test_reorder_unknown_year(self, manage: SundaySchoolManagementService) -> None:
        with pytest.raises(SundaySchoolYearNotFoundError):
            manage.set_order(LessonOrderDTO(year=2030, lesson_ids=[]))

    def test_theme(self, manage: SundaySchoolManagementService) -> None:
        _create(manage)

        year = manage.set_theme(2026, "O Drama das Escrituras")

        assert (year.theme, year.lesson_count, year.published_count) == (
            "O Drama das Escrituras",
            1,
            1,
        )
        with pytest.raises(SundaySchoolYearNotFoundError):
            manage.set_theme(2030, "")
