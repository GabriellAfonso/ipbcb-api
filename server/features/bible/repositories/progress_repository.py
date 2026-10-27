"""ORM persistence of reading progress (specs/025-bible-videos research R-08)."""

from collections.abc import Collection, Sequence
from uuid import UUID

from django.db import transaction

from features.bible.models import BibleChapterProgress, BibleVideo, BibleVideoProgress
from features.bible.progress_dtos import ChapterMarkDTO, VideoMarkDTO

_MARK_FIELDS = ["done", "changed_at"]


class BibleProgressRepositoryImpl:
    """ORM implementation of ``BibleProgressRepository``. Writes are upserts, one statement
    per table, so a 500-item batch costs a fixed number of queries.

    >>> BibleProgressRepositoryImpl().done_video_ids(user_id)
    [7, 42]
    """

    def chapter_marks(self, user_id: UUID, books: Collection[str]) -> list[ChapterMarkDTO]:
        rows = BibleChapterProgress.objects.filter(user_id=user_id, book__in=books)
        return [
            ChapterMarkDTO(book=r.book, chapter=r.chapter, done=r.done, changed_at=r.changed_at)
            for r in rows
        ]

    def video_marks(self, user_id: UUID, video_ids: Collection[int]) -> list[VideoMarkDTO]:
        rows = BibleVideoProgress.objects.filter(user_id=user_id, video_id__in=video_ids)
        return [
            VideoMarkDTO(video_id=r.video_id, done=r.done, changed_at=r.changed_at) for r in rows
        ]

    def existing_video_ids(self, video_ids: Collection[int]) -> set[int]:
        return set(BibleVideo.objects.filter(pk__in=video_ids).values_list("pk", flat=True))

    def save_marks(
        self, user_id: UUID, chapters: Sequence[ChapterMarkDTO], videos: Sequence[VideoMarkDTO]
    ) -> None:
        with transaction.atomic():
            _upsert_chapters(user_id, chapters)
            _upsert_videos(user_id, videos)

    def done_chapters(self, user_id: UUID) -> list[tuple[str, int]]:
        rows = BibleChapterProgress.objects.filter(user_id=user_id, done=True)
        return list(rows.values_list("book", "chapter"))

    def done_video_ids(self, user_id: UUID) -> list[int]:
        rows = BibleVideoProgress.objects.filter(user_id=user_id, done=True)
        return sorted(rows.values_list("video_id", flat=True))


def _upsert_chapters(user_id: UUID, marks: Sequence[ChapterMarkDTO]) -> None:
    if not marks:
        return
    BibleChapterProgress.objects.bulk_create(
        [BibleChapterProgress(user_id=user_id, **mark.model_dump()) for mark in marks],
        update_conflicts=True,
        unique_fields=["user", "book", "chapter"],
        update_fields=_MARK_FIELDS,
    )


def _upsert_videos(user_id: UUID, marks: Sequence[VideoMarkDTO]) -> None:
    if not marks:
        return
    BibleVideoProgress.objects.bulk_create(
        [BibleVideoProgress(user_id=user_id, **mark.model_dump()) for mark in marks],
        update_conflicts=True,
        unique_fields=["user", "video"],
        update_fields=_MARK_FIELDS,
    )
