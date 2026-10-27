"""BibleProgressService with named fakes (specs/025-bible-videos US4)."""

from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest

from features.bible.progress_dtos import (
    ChapterChangeDTO,
    ChapterMarkDTO,
    ProgressChangeDTO,
    RejectedChangeDTO,
    VideoChangeDTO,
)
from features.bible.services.progress_service import BibleProgressService
from features.bible.tests.fakes import SMALL_CANON, FakeBibleProgressRepository, FixedClock

NOW = datetime(2026, 10, 27, 13, 0, tzinfo=UTC)
BRASILIA = timezone(timedelta(hours=-3))
USER = uuid4()


@pytest.fixture
def repository() -> FakeBibleProgressRepository:
    return FakeBibleProgressRepository(video_ids=[7, 42])


@pytest.fixture
def service(repository: FakeBibleProgressRepository) -> BibleProgressService:
    return BibleProgressService(repository, SMALL_CANON, FixedClock(NOW))


def _chapter(book: str, chapter: int, done: bool, at: datetime) -> ChapterChangeDTO:
    return ChapterChangeDTO(type="chapter", book=book, chapter=chapter, done=done, changed_at=at)


def _video(video_id: int, done: bool, at: datetime) -> VideoChangeDTO:
    return VideoChangeDTO(type="video", video_id=video_id, done=done, changed_at=at)


def _minutes_ago(minutes: int) -> datetime:
    return NOW - timedelta(minutes=minutes)


class TestSync:
    def test_valid_changes_are_accepted_and_stored_canonically_in_utc(
        self, service: BibleProgressService, repository: FakeBibleProgressRepository
    ) -> None:
        local = datetime(2026, 10, 27, 9, 0, tzinfo=BRASILIA)
        result = service.sync(USER, [_chapter("gn", 1, True, local), _video(42, True, local)])

        assert result.accepted == [0, 1]
        assert result.rejected == []
        stored = repository.chapters[(USER, "Gn", 1)]
        assert stored.changed_at == datetime(2026, 10, 27, 12, 0, tzinfo=UTC)
        assert stored.changed_at.tzinfo == UTC
        assert repository.done_video_ids(USER) == [42]

    def test_older_change_is_accepted_but_ignored(
        self, service: BibleProgressService, repository: FakeBibleProgressRepository
    ) -> None:
        # Device A unmarked Gn 1 at 10:05; device B, offline, had marked it at 10:00.
        service.sync(USER, [_chapter("Gn", 1, False, _minutes_ago(55))])
        result = service.sync(USER, [_chapter("Gn", 1, True, _minutes_ago(60))])

        assert result.accepted == [0]
        assert repository.chapters[(USER, "Gn", 1)].done is False

    def test_newer_change_overwrites_a_tombstone(
        self, service: BibleProgressService, repository: FakeBibleProgressRepository
    ) -> None:
        service.sync(USER, [_chapter("Gn", 1, False, _minutes_ago(60))])
        service.sync(USER, [_chapter("Gn", 1, True, _minutes_ago(30))])
        assert repository.done_chapters(USER) == [("Gn", 1)]

    def test_same_target_twice_in_one_batch_keeps_the_newest(
        self, service: BibleProgressService, repository: FakeBibleProgressRepository
    ) -> None:
        result = service.sync(
            USER, [_video(7, True, _minutes_ago(1)), _video(7, False, _minutes_ago(9))]
        )
        assert result.accepted == [0, 1]
        assert repository.done_video_ids(USER) == [7]

    @pytest.mark.parametrize(
        ("change", "reason"),
        [
            (_chapter("Xy", 1, True, NOW), "unknown_book"),
            (_chapter("Gn", 51, True, NOW), "unknown_chapter"),
            (_chapter("Gn", 0, True, NOW), "unknown_chapter"),
            (_video(99, True, NOW), "unknown_video"),
            (_chapter("Gn", 1, True, datetime(2026, 10, 27, 13, 0)), "changed_at_without_offset"),
            (_chapter("Gn", 1, True, NOW + timedelta(minutes=6)), "changed_at_in_future"),
        ],
    )
    def test_bad_item_is_rejected_alone(
        self,
        service: BibleProgressService,
        repository: FakeBibleProgressRepository,
        change: ProgressChangeDTO,
        reason: str,
    ) -> None:
        result = service.sync(USER, [_chapter("Gn", 2, True, NOW), change])

        assert result.accepted == [0]
        assert result.rejected == [RejectedChangeDTO(index=1, reason=reason)]
        assert repository.done_chapters(USER) == [("Gn", 2)]

    def test_a_few_minutes_ahead_is_tolerated(self, service: BibleProgressService) -> None:
        result = service.sync(USER, [_chapter("Gn", 1, True, NOW + timedelta(minutes=5))])
        assert result.accepted == [0]

    def test_users_do_not_see_each_other(
        self, service: BibleProgressService, repository: FakeBibleProgressRepository
    ) -> None:
        other = uuid4()
        repository.chapters[(other, "Gn", 1)] = ChapterMarkDTO(
            book="Gn", chapter=1, done=True, changed_at=_minutes_ago(1)
        )
        service.sync(USER, [_chapter("Gn", 1, False, _minutes_ago(30))])
        assert repository.chapters[(other, "Gn", 1)].done is True
        assert repository.chapters[(USER, "Gn", 1)].done is False


class TestState:
    def test_only_done_items_books_in_canonical_order(self, service: BibleProgressService) -> None:
        service.sync(
            USER,
            [
                _chapter("Sl", 23, True, NOW),
                _chapter("Gn", 3, True, NOW),
                _chapter("Gn", 1, True, NOW),
                _chapter("Êx", 1, False, NOW),
                _video(42, True, NOW),
                _video(7, False, NOW),
            ],
        )
        state = service.state(USER)
        assert state.chapters == {"Gn": [1, 3], "Sl": [23]}
        assert list(state.chapters) == ["Gn", "Sl"]
        assert state.videos == [42]
