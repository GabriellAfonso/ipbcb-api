"""Bible videos: saving a YouTube link to places, editing places and order
(specs/025-bible-videos)."""

from collections.abc import Sequence
from uuid import UUID

from core.domain.bible_exceptions import place_label
from core.domain.exceptions import (
    BiblePlaceInvalidError,
    BiblePlaceNotFoundError,
    BibleVideoExistsError,
    BibleVideoInvalidUrlError,
    BibleVideoNotFoundError,
    BibleVideoOrderMismatchError,
)
from features.bible.domain.canon import BibleCanon, BiblePlace
from features.bible.domain.youtube_links import YouTubeTarget, parse_youtube_link
from features.bible.repositories.interfaces import BibleVideoRepository, YouTubeMetadataClient
from features.bible.services.place_rules import canonical_place, canonical_places, sorted_places
from features.bible.video_dtos import (
    BiblePlaceDTO,
    BibleVideoCreateDTO,
    BibleVideoDTO,
    BibleVideoNewDTO,
    BibleVideoOrderDTO,
)


def _place_set(video: BibleVideoDTO) -> set[BiblePlace]:
    return {BiblePlace(place.book, place.chapter) for place in video.places}


class BibleVideoService:
    """Use cases of Bible videos. Every video returned has its places in canonical order.

    >>> service.create(BibleVideoCreateDTO(url="youtu.be/dQw4w9WgXcQ",
    ...     places=[BiblePlaceDTO(book="Gn", chapter=1)]), creator_id)
    BibleVideoDTO(id=42, ...)
    """

    def __init__(
        self,
        repository: BibleVideoRepository,
        youtube: YouTubeMetadataClient,
        canon: BibleCanon,
    ) -> None:
        self._repo = repository
        self._youtube = youtube
        self._canon = canon

    def list_videos(self) -> list[BibleVideoDTO]:
        return [self._ordered(video) for video in self._repo.list_all()]

    def create(self, dto: BibleVideoCreateDTO, creator_id: UUID) -> BibleVideoDTO:
        """Duplicate check before the YouTube call (research R-06); a duplicate raises
        ``BibleVideoExistsError`` carrying the saved video."""
        target = parse_youtube_link(dto.url)
        if target is None:
            raise BibleVideoInvalidUrlError(dto.url)
        places = self._new_places(dto.places)
        self._refuse_duplicate(target)
        created = self._repo.create(self._new_video(target), places, creator_id)
        if created is None:
            # Another leader saved the same target between the check and the insert.
            self._refuse_duplicate(target)
            raise RuntimeError(f"Video {target.youtube_id!r} was neither created nor found.")
        return self._ordered(created)

    def replace_places(
        self, video_id: int, places: Sequence[BiblePlaceDTO]
    ) -> BibleVideoDTO | None:
        """Kept places keep their position, new ones go last, missing ones are removed. An
        empty list deletes the video and returns None."""
        current = _place_set(self._existing(video_id))
        desired = canonical_places(self._canon, places)
        if not desired:
            self._repo.delete(video_id)
            return None
        added = [place for place in desired if place not in current]
        self._repo.change_places(video_id, added, current - set(desired))
        return self._ordered(self._existing(video_id))

    def remove_place(self, video_id: int, book: str, chapter: int | None) -> BibleVideoDTO | None:
        """Remove one place. The last one deletes the video and returns None."""
        current = _place_set(self._existing(video_id))
        place = canonical_place(self._canon, book, chapter)
        if place not in current:
            raise BiblePlaceNotFoundError(video_id, place.book, place.chapter)
        if current == {place}:
            self._repo.delete(video_id)
            return None
        self._repo.change_places(video_id, [], {place})
        return self._ordered(self._existing(video_id))

    def delete(self, video_id: int) -> None:
        self._existing(video_id)
        self._repo.delete(video_id)

    def set_order(self, dto: BibleVideoOrderDTO) -> None:
        """The list must be exactly the videos of that place, each once."""
        place = canonical_place(self._canon, dto.book, dto.chapter)
        expected = self._repo.video_ids_at(place)
        if sorted(dto.video_ids) != sorted(expected):
            label = place_label(place.book, place.chapter)
            raise BibleVideoOrderMismatchError(label, expected, dto.video_ids)
        self._repo.set_order(place, dto.video_ids)

    def _new_places(self, places: Sequence[BiblePlaceDTO]) -> list[BiblePlace]:
        resolved = canonical_places(self._canon, places)
        if not resolved:
            raise BiblePlaceInvalidError("Escolha ao menos um capítulo ou livro para o vídeo.")
        return resolved

    def _refuse_duplicate(self, target: YouTubeTarget) -> None:
        existing = self._repo.find_by_target(target.kind, target.youtube_id)
        if existing is not None:
            raise BibleVideoExistsError(self._ordered(existing).model_dump(mode="json"))

    def _new_video(self, target: YouTubeTarget) -> BibleVideoNewDTO:
        metadata = self._youtube.fetch(target)
        return BibleVideoNewDTO(
            kind=target.kind,
            youtube_id=target.youtube_id,
            url=target.url,
            title=metadata.title,
            thumbnail_url=metadata.thumbnail_url,
        )

    def _existing(self, video_id: int) -> BibleVideoDTO:
        video = self._repo.get(video_id)
        if video is None:
            raise BibleVideoNotFoundError(video_id)
        return video

    def _ordered(self, video: BibleVideoDTO) -> BibleVideoDTO:
        return video.model_copy(update={"places": sorted_places(self._canon, video.places)})
