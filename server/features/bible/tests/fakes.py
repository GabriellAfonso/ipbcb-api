"""Named in-memory fakes for the Bible videos and progress ports (CLAUDE.md §10)."""

from collections.abc import Collection, Sequence
from datetime import datetime
from itertools import count
from uuid import UUID

from core.domain.exceptions import BibleVideoLookupFailedError, BibleVideoUnavailableError
from features.bible.domain.canon import BibleCanon, BiblePlace
from features.bible.domain.youtube_links import YouTubeKind, YouTubeTarget
from features.bible.progress_dtos import ChapterMarkDTO, VideoMarkDTO
from features.bible.video_dtos import (
    BibleVideoDTO,
    BibleVideoNewDTO,
    BibleVideoPlaceDTO,
    YouTubeMetadataDTO,
)

# A small canon for unit tests; the integration tests use the real 66 books.
SMALL_CANON = BibleCanon({"Gn": 50, "Êx": 40, "Jo": 21, "Jó": 42, "Sl": 150})


class FixedClock:
    """A clock stopped at ``now_value``; tests move it by assigning."""

    def __init__(self, now: datetime) -> None:
        self.now_value = now

    def now(self) -> datetime:
        return self.now_value


class FakeYouTubeMetadataClient:
    """Answers with ``title`` unless told to refuse or fail; records every target asked."""

    def __init__(self, title: str = "Estudo em Gênesis") -> None:
        self.title = title
        self.unavailable = False
        self.failing = False
        self.fetched: list[YouTubeTarget] = []

    def fetch(self, target: YouTubeTarget) -> YouTubeMetadataDTO:
        self.fetched.append(target)
        if self.unavailable:
            raise BibleVideoUnavailableError(target.youtube_id, 404)
        if self.failing:
            raise BibleVideoLookupFailedError("ReadTimeout")
        return YouTubeMetadataDTO(
            title=self.title, thumbnail_url=f"https://thumb.test/{target.youtube_id}.jpg"
        )


class FakeBibleVideoRepository:
    """Videos and places in dicts, appending and ordering like the real repository."""

    def __init__(self) -> None:
        self.videos: dict[int, BibleVideoNewDTO] = {}
        # (video_id, place) -> position
        self.positions: dict[tuple[int, BiblePlace], int] = {}
        self.lose_create_race = False
        self._ids = count(1)

    def add(self, youtube_id: str, places: Sequence[BiblePlace]) -> BibleVideoDTO:
        """Seed a video appended to ``places``."""
        video = BibleVideoNewDTO(
            kind=YouTubeKind.VIDEO,
            youtube_id=youtube_id,
            url=f"https://www.youtube.com/watch?v={youtube_id}",
            title=f"Vídeo {youtube_id}",
            thumbnail_url="https://thumb.test/x.jpg",
        )
        return self._insert(video, places)

    def list_all(self) -> list[BibleVideoDTO]:
        return [self._dto(video_id) for video_id in sorted(self.videos)]

    def get(self, video_id: int) -> BibleVideoDTO | None:
        return self._dto(video_id) if video_id in self.videos else None

    def find_by_target(self, kind: YouTubeKind, youtube_id: str) -> BibleVideoDTO | None:
        for video_id, video in self.videos.items():
            if video.kind is kind and video.youtube_id == youtube_id:
                return self._dto(video_id)
        return None

    def create(
        self, video: BibleVideoNewDTO, places: Sequence[BiblePlace], creator_id: UUID
    ) -> BibleVideoDTO | None:
        if self.lose_create_race:
            self._insert(video, places)
            return None
        return self._insert(video, places)

    def change_places(
        self, video_id: int, added: Sequence[BiblePlace], removed: Collection[BiblePlace]
    ) -> None:
        for place in removed:
            del self.positions[(video_id, place)]
        self._append(video_id, added)

    def delete(self, video_id: int) -> None:
        del self.videos[video_id]
        self.positions = {key: pos for key, pos in self.positions.items() if key[0] != video_id}

    def video_ids_at(self, place: BiblePlace) -> list[int]:
        at_place = [(pos, vid) for (vid, p), pos in self.positions.items() if p == place]
        return [vid for _, vid in sorted(at_place)]

    def set_order(self, place: BiblePlace, video_ids: Sequence[int]) -> None:
        for index, video_id in enumerate(video_ids):
            self.positions[(video_id, place)] = index

    def _insert(self, video: BibleVideoNewDTO, places: Sequence[BiblePlace]) -> BibleVideoDTO:
        video_id = next(self._ids)
        self.videos[video_id] = video
        self._append(video_id, places)
        return self._dto(video_id)

    def _append(self, video_id: int, places: Sequence[BiblePlace]) -> None:
        for place in places:
            taken = [pos for (_, p), pos in self.positions.items() if p == place]
            self.positions[(video_id, place)] = max(taken, default=-1) + 1

    def _dto(self, video_id: int) -> BibleVideoDTO:
        places = [
            BibleVideoPlaceDTO(book=p.book, chapter=p.chapter, position=pos)
            for (vid, p), pos in self.positions.items()
            if vid == video_id
        ]
        return BibleVideoDTO(id=video_id, **self.videos[video_id].model_dump(), places=places)


class FakeBibleProgressRepository:
    """One user's marks in dicts (the tests use a single user unless stated)."""

    def __init__(self, video_ids: Collection[int] = ()) -> None:
        self.chapters: dict[tuple[UUID, str, int], ChapterMarkDTO] = {}
        self.videos: dict[tuple[UUID, int], VideoMarkDTO] = {}
        self.known_video_ids = set(video_ids)
        self.saved_batches = 0

    def chapter_marks(self, user_id: UUID, books: Collection[str]) -> list[ChapterMarkDTO]:
        return [m for (u, b, _), m in self.chapters.items() if u == user_id and b in books]

    def video_marks(self, user_id: UUID, video_ids: Collection[int]) -> list[VideoMarkDTO]:
        return [m for (u, v), m in self.videos.items() if u == user_id and v in video_ids]

    def existing_video_ids(self, video_ids: Collection[int]) -> set[int]:
        return self.known_video_ids & set(video_ids)

    def save_marks(
        self, user_id: UUID, chapters: Sequence[ChapterMarkDTO], videos: Sequence[VideoMarkDTO]
    ) -> None:
        self.saved_batches += 1
        for chapter in chapters:
            self.chapters[(user_id, chapter.book, chapter.chapter)] = chapter
        for video in videos:
            self.videos[(user_id, video.video_id)] = video

    def done_chapters(self, user_id: UUID) -> list[tuple[str, int]]:
        return [(b, c) for (u, b, c), m in self.chapters.items() if u == user_id and m.done]

    def done_video_ids(self, user_id: UUID) -> list[int]:
        return sorted(v for (u, v), m in self.videos.items() if u == user_id and m.done)
