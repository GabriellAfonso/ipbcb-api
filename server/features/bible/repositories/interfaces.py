"""Ports of Bible videos and progress (specs/025-bible-videos). ORM and HTTP stay behind them."""

from collections.abc import Collection, Sequence
from typing import Protocol
from uuid import UUID

from features.bible.domain.canon import BiblePlace
from features.bible.domain.youtube_links import YouTubeKind, YouTubeTarget
from features.bible.progress_dtos import ChapterMarkDTO, VideoMarkDTO
from features.bible.video_dtos import BibleVideoDTO, BibleVideoNewDTO, YouTubeMetadataDTO


class BibleVideoRepository(Protocol):
    """Persistence of videos and their places. Places come back unsorted; the service orders
    them by the canon."""

    def list_all(self) -> list[BibleVideoDTO]:
        """Every video with its places, by id."""
        ...

    def get(self, video_id: int) -> BibleVideoDTO | None: ...

    def find_by_target(self, kind: YouTubeKind, youtube_id: str) -> BibleVideoDTO | None: ...

    def create(
        self, video: BibleVideoNewDTO, places: Sequence[BiblePlace], creator_id: UUID
    ) -> BibleVideoDTO | None:
        """Insert the video and append it to the end of each place. None when another request
        saved the same target first (unique constraint)."""
        ...

    def change_places(
        self, video_id: int, added: Sequence[BiblePlace], removed: Collection[BiblePlace]
    ) -> None:
        """Delete ``removed`` and append ``added`` at the end of their places, atomically."""
        ...

    def delete(self, video_id: int) -> None: ...

    def video_ids_at(self, place: BiblePlace) -> list[int]:
        """Ids of the videos in ``place``, in their current order."""
        ...

    def set_order(self, place: BiblePlace, video_ids: Sequence[int]) -> None:
        """Positions ``0..n-1`` in ``place`` following ``video_ids``."""
        ...


class BibleProgressRepository(Protocol):
    """Persistence of one user's chapter and video marks, tombstones included."""

    def chapter_marks(self, user_id: UUID, books: Collection[str]) -> list[ChapterMarkDTO]: ...

    def video_marks(self, user_id: UUID, video_ids: Collection[int]) -> list[VideoMarkDTO]: ...

    def existing_video_ids(self, video_ids: Collection[int]) -> set[int]: ...

    def save_marks(
        self, user_id: UUID, chapters: Sequence[ChapterMarkDTO], videos: Sequence[VideoMarkDTO]
    ) -> None:
        """Insert or overwrite each mark, in one transaction."""
        ...

    def done_chapters(self, user_id: UUID) -> list[tuple[str, int]]: ...

    def done_video_ids(self, user_id: UUID) -> list[int]: ...


class YouTubeMetadataClient(Protocol):
    """Title and thumbnail of a video or playlist, read from YouTube."""

    def fetch(self, target: YouTubeTarget) -> YouTubeMetadataDTO:
        """Raise ``BibleVideoUnavailableError`` when YouTube refuses the target and
        ``BibleVideoLookupFailedError`` when it cannot be asked."""
        ...
