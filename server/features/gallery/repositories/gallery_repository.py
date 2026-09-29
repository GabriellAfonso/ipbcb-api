from collections.abc import Iterator, Mapping, Sequence
from datetime import datetime

from django.db import IntegrityError, transaction
from django.db.models import Count, Max, Prefetch, Q, QuerySet

from core.domain.exceptions import AlbumNotFoundError, ClientUploadIdTakenError
from core.time.clock import Clock
from features.gallery.dtos.gallery_dtos import ClientUploadMatch, NewPhoto, PhotoView
from features.gallery.dtos.tag_dtos import MemberRef
from features.gallery.models.gallery import Album, Photo
from features.gallery.models.tags import PhotoTag


class GalleryRepositoryImpl:
    """Live gallery photos through the Django ORM (``Photo.objects`` hides trashed rows).

    Every write sets ``updated_at`` from the injected clock (specs/014-gallery-trash-sync R-06).
    """

    def __init__(self, clock: Clock) -> None:
        self._clock = clock

    def list_all_photos(self, member_ids: frozenset[int] = frozenset()) -> list[PhotoView]:
        """Every photo by position within its album; the service orders albums by tree. With
        ``member_ids``, only photos tagged with every one of them.

        >>> repository.list_all_photos(frozenset({12, 40}))[0].members
        [MemberRef(id=40, name='João Lima'), MemberRef(id=12, name='Maria Souza')]
        """
        return [_to_view(photo) for photo in _filter_by_members(_photos(), member_ids)]

    def list_photos_by_album(
        self, album_id: int, member_ids: frozenset[int] = frozenset()
    ) -> list[PhotoView]:
        photos = _filter_by_members(_photos().filter(album_id=album_id), member_ids)
        return [_to_view(photo) for photo in photos]

    def list_photos_changed_since(self, since: datetime) -> list[PhotoView]:
        """Live photos whose resource changed strictly after ``since`` (the change feed).

        >>> repository.list_photos_changed_since(cursor_instant)[0].updated_at > cursor_instant
        True
        """
        return [_to_view(photo) for photo in _photos().filter(updated_at__gt=since)]

    def get_photo(self, photo_id: int) -> PhotoView | None:
        photo = _photos().filter(pk=photo_id).first()
        return _to_view(photo) if photo else None

    def find_client_upload(self, client_upload_id: str) -> ClientUploadMatch | None:
        """The row carrying ``client_upload_id``, trashed included: ``all_objects``, because a
        retry of a photo sent to the trash must be told so (specs/016 research R-03).

        >>> repository.find_client_upload("3f2a9c1e-7b4d-4e8a-9f10-2c6b5d7e8a90")
        ClientUploadMatch(photo_id=41, trashed=False)
        """
        row = (
            Photo.all_objects.filter(client_upload_id=client_upload_id)
            .values_list("pk", "deleted_at")
            .first()
        )
        return (
            None if row is None else ClientUploadMatch(photo_id=row[0], trashed=row[1] is not None)
        )

    def create_photo(self, photo: NewPhoto) -> PhotoView:
        """Insert the row last in its album. The files are already stored.

        Raises ``ClientUploadIdTakenError`` when a concurrent upload stored the same client
        upload id first: the unique constraint decides the race (specs/016 research R-04).
        """
        try:
            with transaction.atomic():
                created = self._insert_photo(photo)
        except IntegrityError:
            # Checked by row, not by parsing the constraint name out of a driver message,
            # which differs between PostgreSQL and SQLite.
            if photo.client_upload_id and self.find_client_upload(photo.client_upload_id):
                raise ClientUploadIdTakenError(photo.client_upload_id) from None
            raise
        return _to_view(_photos().get(pk=created.pk))

    def _insert_photo(self, photo: NewPhoto) -> Photo:
        return Photo.objects.create(
            album_id=photo.album_id,
            image=photo.image_name,
            thumbnail=photo.thumbnail_name,
            name=photo.name,
            date_taken=photo.date_taken,
            uploaded_by_id=photo.uploader_id,
            position=_next_photo_position(photo.album_id),
            updated_at=self._clock.now(),
            client_upload_id=photo.client_upload_id,
        )

    def update_photo(self, photo_id: int, fields: Mapping[str, object]) -> None:
        Photo.objects.filter(pk=photo_id).update(**fields, updated_at=self._clock.now())

    def move_photo(self, photo_id: int, album_id: int) -> None:
        with transaction.atomic():
            position = _next_photo_position(album_id)
            Photo.objects.filter(pk=photo_id).update(
                album_id=album_id, position=position, updated_at=self._clock.now()
            )

    def photo_ids(self, album_id: int) -> list[int]:
        return list(Photo.objects.filter(album_id=album_id).values_list("id", flat=True))

    def apply_order(self, ids: Sequence[int]) -> None:
        """Write only the photos whose position changes, so the feed reports exactly those."""
        current = dict(Photo.objects.filter(pk__in=ids).values_list("id", "position"))
        now = self._clock.now()
        moved = [
            Photo(pk=photo_id, position=index, updated_at=now)
            for index, photo_id in enumerate(ids)
            if current.get(photo_id) != index
        ]
        with transaction.atomic():
            Photo.objects.bulk_update(moved, ["position", "updated_at"])

    def photos_without_thumbnail(self) -> Iterator[tuple[int, int, str]]:
        """(id, album id, original name) of each photo lacking a thumbnail, read in batches."""
        rows = (
            Photo.objects.filter(thumbnail="").order_by("id").values_list("id", "album_id", "image")
        )
        yield from rows.iterator(chunk_size=100)

    def set_thumbnail(self, photo_id: int, name: str) -> None:
        Photo.objects.filter(pk=photo_id).update(thumbnail=name, updated_at=self._clock.now())


def _photos() -> QuerySet[Photo]:
    """Every Photo resource is built from this query, so each carries its tags: one extra query
    for all of them, member names through the tag's relation (specs/015 research R-06)."""
    tags = PhotoTag.objects.select_related("member").order_by("member__name", "member_id")
    return (
        Photo.objects.select_related("album")
        .prefetch_related(Prefetch("tags", queryset=tags))
        .order_by("position", "id")
    )


def _filter_by_members(photos: QuerySet[Photo], member_ids: frozenset[int]) -> QuerySet[Photo]:
    """Photos tagged with **every** member of ``member_ids`` (AND), in one join: count the
    distinct matching members per photo and keep those that match them all (R-05)."""
    if not member_ids:
        return photos
    matching = Q(tags__member_id__in=member_ids)
    return photos.annotate(
        matched_members=Count("tags__member", filter=matching, distinct=True)
    ).filter(matched_members=len(member_ids))


def _next_photo_position(album_id: int) -> int:
    """Lock the live album row so concurrent appends into it serialize, then take the next slot.

    The lock query goes through the live manager, which re-checks ``deleted_at`` after waiting: an
    album trashed meanwhile yields no row and the photo is refused instead of landing under a
    trashed album (specs/014-gallery-trash-sync research R-02).
    """
    locked = Album.objects.select_for_update().filter(pk=album_id).values_list("pk", flat=True)
    if not list(locked):
        raise AlbumNotFoundError(album_id)
    last = Photo.objects.filter(album_id=album_id).aggregate(last=Max("position"))["last"]
    return 0 if last is None else last + 1


def _to_view(photo: Photo) -> PhotoView:
    return PhotoView(
        id=photo.pk,
        name=photo.name,
        description=photo.description,
        album_id=photo.album_id,
        album_name=photo.album.name,
        image_path=photo.image.url if photo.image else None,
        thumbnail_path=photo.thumbnail.url if photo.thumbnail else None,
        date_taken=photo.date_taken,
        uploaded_at=photo.uploaded_at,
        position=photo.position,
        updated_at=photo.updated_at,
        members=[MemberRef(id=tag.member_id, name=tag.member.name) for tag in photo.tags.all()],
    )
