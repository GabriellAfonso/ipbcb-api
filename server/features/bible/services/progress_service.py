"""Reading progress: the user's marks and the offline-queue sync (specs/025-bible-videos US4)."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID

from core.time.clock import Clock
from features.bible.domain.canon import BibleCanon
from features.bible.domain.last_write_wins import winning_changes
from features.bible.progress_dtos import (
    REASON_IN_FUTURE,
    REASON_UNKNOWN_BOOK,
    REASON_UNKNOWN_CHAPTER,
    REASON_UNKNOWN_VIDEO,
    REASON_WITHOUT_OFFSET,
    ChapterChangeDTO,
    ChapterMarkDTO,
    ProgressChangeDTO,
    ProgressStateDTO,
    ProgressSyncResultDTO,
    RejectedChangeDTO,
    VideoChangeDTO,
    VideoMarkDTO,
)
from features.bible.repositories.interfaces import BibleProgressRepository

# Guards against a broken device clock only; skew between devices is accepted (spec, Assumptions).
FUTURE_TOLERANCE = timedelta(minutes=5)

Mark = ChapterMarkDTO | VideoMarkDTO


class BibleProgressService:
    """Use cases of reading progress.

    >>> service.sync(user_id, [ChapterChangeDTO(type="chapter", book="gn", chapter=1,
    ...     done=True, changed_at=datetime(2026, 10, 27, 13, tzinfo=UTC))])
    ProgressSyncResultDTO(accepted=[0], rejected=[])
    """

    def __init__(
        self, repository: BibleProgressRepository, canon: BibleCanon, clock: Clock
    ) -> None:
        self._repo = repository
        self._canon = canon
        self._clock = clock

    def state(self, user_id: UUID) -> ProgressStateDTO:
        """Done items only; books in canonical order, chapters and video ids ascending."""
        order = {book: index for index, book in enumerate(self._canon.books)}
        chapters: dict[str, list[int]] = {}
        for book, chapter in sorted(
            self._repo.done_chapters(user_id), key=lambda row: (order.get(row[0], 0), row[1])
        ):
            chapters.setdefault(book, []).append(chapter)
        return ProgressStateDTO(chapters=chapters, videos=self._repo.done_video_ids(user_id))

    def sync(self, user_id: UUID, changes: Sequence[ProgressChangeDTO]) -> ProgressSyncResultDTO:
        """Validate each change, then keep only those newer than what is stored (FR-018)."""
        marks, rejected = self._validated(changes)
        chapters = [m for m in marks.values() if isinstance(m, ChapterMarkDTO)]
        videos = [m for m in marks.values() if isinstance(m, VideoMarkDTO)]
        self._repo.save_marks(
            user_id, self._chapter_winners(user_id, chapters), self._video_winners(user_id, videos)
        )
        return ProgressSyncResultDTO(accepted=sorted(marks), rejected=rejected)

    def _validated(
        self, changes: Sequence[ProgressChangeDTO]
    ) -> tuple[dict[int, Mark], list[RejectedChangeDTO]]:
        """Accepted marks by batch index, in batch order, and the rejections."""
        video_ids = {c.video_id for c in changes if isinstance(c, VideoChangeDTO)}
        known_videos = self._repo.existing_video_ids(video_ids) if video_ids else set()
        now = self._clock.now()
        marks: dict[int, Mark] = {}
        rejected: list[RejectedChangeDTO] = []
        for index, change in enumerate(changes):
            mark_or_reason = self._to_mark(change, known_videos, now)
            if isinstance(mark_or_reason, str):
                rejected.append(RejectedChangeDTO(index=index, reason=mark_or_reason))
            else:
                marks[index] = mark_or_reason
        return marks, rejected

    def _to_mark(
        self, change: ProgressChangeDTO, known_videos: set[int], now: datetime
    ) -> Mark | str:
        reason = _time_problem(change.changed_at, now)
        if reason is not None:
            return reason
        changed_at = change.changed_at.astimezone(UTC)
        if isinstance(change, VideoChangeDTO):
            if change.video_id not in known_videos:
                return REASON_UNKNOWN_VIDEO
            return VideoMarkDTO(video_id=change.video_id, done=change.done, changed_at=changed_at)
        return self._chapter_mark(change, changed_at)

    def _chapter_mark(self, change: ChapterChangeDTO, changed_at: datetime) -> Mark | str:
        book = self._canon.resolve(change.book)
        if book is None:
            return REASON_UNKNOWN_BOOK
        if not self._canon.has_chapter(book, change.chapter):
            return REASON_UNKNOWN_CHAPTER
        return ChapterMarkDTO(
            book=book, chapter=change.chapter, done=change.done, changed_at=changed_at
        )

    def _chapter_winners(
        self, user_id: UUID, marks: Sequence[ChapterMarkDTO]
    ) -> list[ChapterMarkDTO]:
        if not marks:
            return []
        stored = self._repo.chapter_marks(user_id, {m.book for m in marks})
        stored_at = {(m.book, m.chapter): m.changed_at for m in stored}
        return winning_changes(stored_at, [((m.book, m.chapter), m) for m in marks])

    def _video_winners(self, user_id: UUID, marks: Sequence[VideoMarkDTO]) -> list[VideoMarkDTO]:
        if not marks:
            return []
        stored = self._repo.video_marks(user_id, {m.video_id for m in marks})
        stored_at = {m.video_id: m.changed_at for m in stored}
        return winning_changes(stored_at, [(m.video_id, m) for m in marks])


def _time_problem(changed_at: datetime, now: datetime) -> str | None:
    if changed_at.tzinfo is None or changed_at.utcoffset() is None:
        return REASON_WITHOUT_OFFSET
    if changed_at > now + FUTURE_TOLERANCE:
        return REASON_IN_FUTURE
    return None
