"""ORM persistence of Bible videos and places (specs/025-bible-videos data-model)."""

from collections.abc import Collection, Iterable, Sequence
from functools import reduce
from operator import or_
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import Max, Q, QuerySet
from django.utils import timezone

from features.bible.domain.canon import BiblePlace
from features.bible.domain.youtube_links import YouTubeKind
from features.bible.models import BibleVideo, BibleVideoPlace
from features.bible.video_dtos import BibleVideoDTO, BibleVideoNewDTO, BibleVideoPlaceDTO


def _place_filter(places: Iterable[BiblePlace]) -> Q:
    # chapter=None must become chapter__isnull: Q(chapter=None) also works in Django, but
    # spelling it out keeps the whole-book case obvious.
    conditions = [
        Q(book=place.book, chapter__isnull=True)
        if place.chapter is None
        else Q(book=place.book, chapter=place.chapter)
        for place in places
    ]
    return reduce(or_, conditions, Q(pk__in=[]))


def _next_positions(places: Sequence[BiblePlace]) -> dict[BiblePlace, int]:
    """First free position in each place: one grouped query (research R-07)."""
    rows = (
        BibleVideoPlace.objects.filter(_place_filter(places))
        .values("book", "chapter")
        .annotate(last=Max("position"))
    )
    taken = {BiblePlace(row["book"], row["chapter"]): row["last"] + 1 for row in rows}
    return {place: taken.get(place, 0) for place in places}


def _append(video_id: int, places: Sequence[BiblePlace]) -> None:
    if not places:
        return
    positions = _next_positions(places)
    BibleVideoPlace.objects.bulk_create(
        BibleVideoPlace(video_id=video_id, book=p.book, chapter=p.chapter, position=positions[p])
        for p in places
    )


def _with_places() -> QuerySet[BibleVideo]:
    return BibleVideo.objects.prefetch_related("places")


def _to_dto(video: BibleVideo) -> BibleVideoDTO:
    return BibleVideoDTO(
        id=video.pk,
        kind=YouTubeKind(video.kind),
        youtube_id=video.youtube_id,
        url=video.url,
        title=video.title,
        thumbnail_url=video.thumbnail_url,
        places=[
            BibleVideoPlaceDTO(book=p.book, chapter=p.chapter, position=p.position)
            for p in video.places.all()
        ],
    )


class BibleVideoRepositoryImpl:
    """ORM implementation of ``BibleVideoRepository``.

    >>> BibleVideoRepositoryImpl().find_by_target(YouTubeKind.VIDEO, "dQw4w9WgXcQ")
    BibleVideoDTO(id=42, ...)
    """

    def list_all(self) -> list[BibleVideoDTO]:
        return [_to_dto(video) for video in _with_places().order_by("id")]

    def get(self, video_id: int) -> BibleVideoDTO | None:
        video = _with_places().filter(pk=video_id).first()
        return _to_dto(video) if video else None

    def find_by_target(self, kind: YouTubeKind, youtube_id: str) -> BibleVideoDTO | None:
        video = _with_places().filter(kind=kind.value, youtube_id=youtube_id).first()
        return _to_dto(video) if video else None

    def create(
        self, video: BibleVideoNewDTO, places: Sequence[BiblePlace], creator_id: UUID
    ) -> BibleVideoDTO | None:
        try:
            with transaction.atomic():
                row = BibleVideo.objects.create(**video.model_dump(), created_by_id=creator_id)
                _append(row.pk, places)
        except IntegrityError:
            return None
        return self.get(row.pk)

    def change_places(
        self, video_id: int, added: Sequence[BiblePlace], removed: Collection[BiblePlace]
    ) -> None:
        with transaction.atomic():
            if removed:
                BibleVideoPlace.objects.filter(_place_filter(removed), video_id=video_id).delete()
            _append(video_id, added)
            _touch(video_id)

    def delete(self, video_id: int) -> None:
        BibleVideo.objects.filter(pk=video_id).delete()

    def video_ids_at(self, place: BiblePlace) -> list[int]:
        rows = BibleVideoPlace.objects.filter(_place_filter([place])).order_by(
            "position", "video_id"
        )
        return list(rows.values_list("video_id", flat=True))

    def set_order(self, place: BiblePlace, video_ids: Sequence[int]) -> None:
        position_of = {video_id: index for index, video_id in enumerate(video_ids)}
        rows = list(BibleVideoPlace.objects.filter(_place_filter([place])))
        for row in rows:
            row.position = position_of[row.video_id]
        BibleVideoPlace.objects.bulk_update(rows, ["position"])


def _touch(video_id: int) -> None:
    """Bump ``updated_at``: a place change is a change of the video."""
    BibleVideo.objects.filter(pk=video_id).update(updated_at=timezone.now())
