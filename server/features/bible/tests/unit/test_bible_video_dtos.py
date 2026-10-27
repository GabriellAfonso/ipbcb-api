"""Strict DTOs of feature 025, the canon built from the translations, and the new exceptions."""

import pytest
from pydantic import ValidationError

from core.domain.exceptions import BibleVideoExistsError, BibleVideoLookupFailedError
from core.http.exceptions import custom_exception_handler
from features.bible.dtos import BibleBook
from features.bible.progress_dtos import ChapterChangeDTO, ProgressSyncDTO, VideoChangeDTO
from features.bible.repositories.bible_text import BibleRepositoryImpl, shared_chapter_counts
from features.bible.video_dtos import BiblePlaceDTO, BibleVideoCreateDTO

CHANGED_AT = "2026-10-27T10:00:00-03:00"


def _chapter_item(**extra: object) -> dict[str, object]:
    return {
        "type": "chapter",
        "book": "Gn",
        "chapter": 1,
        "done": True,
        "changed_at": CHANGED_AT,
        **extra,
    }


class TestProgressSyncDTO:
    def test_items_are_told_apart_by_type(self) -> None:
        dto = ProgressSyncDTO.model_validate(
            {
                "changes": [
                    _chapter_item(),
                    {"type": "video", "video_id": 4, "done": False, "changed_at": CHANGED_AT},
                ]
            }
        )
        assert isinstance(dto.changes[0], ChapterChangeDTO)
        assert isinstance(dto.changes[1], VideoChangeDTO)

    @pytest.mark.parametrize(
        "changes",
        [
            [],
            [_chapter_item()] * 501,
            [_chapter_item(extra="x")],
            [{"type": "book", "book": "Gn", "done": True, "changed_at": CHANGED_AT}],
            [{"type": "video", "done": True, "changed_at": CHANGED_AT}],
            [_chapter_item(changed_at="ontem")],
        ],
    )
    def test_shape_errors_refuse_the_batch(self, changes: list[object]) -> None:
        with pytest.raises(ValidationError):
            ProgressSyncDTO.model_validate({"changes": changes})

    def test_a_full_batch_of_500_is_accepted(self) -> None:
        assert (
            len(ProgressSyncDTO.model_validate({"changes": [_chapter_item()] * 500}).changes) == 500
        )


class TestVideoDTOs:
    def test_place_chapter_must_be_given_and_positive(self) -> None:
        with pytest.raises(ValidationError):
            BiblePlaceDTO.model_validate({"book": "Gn"})
        with pytest.raises(ValidationError):
            BiblePlaceDTO(book="Gn", chapter=0)
        assert BiblePlaceDTO(book="Gn", chapter=None).chapter is None

    def test_create_refuses_unknown_fields(self) -> None:
        with pytest.raises(ValidationError):
            BibleVideoCreateDTO.model_validate({"url": "x", "places": [], "title": "mine"})


class TestSharedChapterCounts:
    def _book(self, abbrev: str, chapters: int) -> BibleBook:
        return BibleBook(abbrev=abbrev, name=abbrev, chapters=[["v"]] * chapters)

    def test_translations_that_agree_give_the_counts(self) -> None:
        books = [self._book("Gn", 2), self._book("Êx", 1)]
        assert shared_chapter_counts({"A": books, "B": books}) == {"Gn": 2, "Êx": 1}

    def test_translations_that_disagree_fail_loading(self) -> None:
        with pytest.raises(ValueError, match="disagree"):
            shared_chapter_counts({"A": [self._book("Gn", 2)], "B": [self._book("Gn", 3)]})

    def test_real_data_has_66_books_with_served_identifiers(self) -> None:
        canon = BibleRepositoryImpl().canon()
        assert len(canon.books) == 66
        assert canon.books[:2] == ["Gn", "Êx"]
        assert canon.resolve("1tn") == "1Tn"
        assert canon.has_chapter("Sl", 150) and not canon.has_chapter("Sl", 151)


class TestExceptionResponses:
    def test_exists_carries_the_video(self) -> None:
        response = custom_exception_handler(BibleVideoExistsError({"id": 42}), {})
        assert response.status_code == 409
        assert response.data["error_code"] == "BIBLE_VIDEO_EXISTS"
        assert response.data["video"] == {"id": 42}

    def test_lookup_failure_is_503(self) -> None:
        response = custom_exception_handler(BibleVideoLookupFailedError("ReadTimeout"), {})
        assert response.status_code == 503
        assert response.data["error_code"] == "BIBLE_VIDEO_LOOKUP_FAILED"
