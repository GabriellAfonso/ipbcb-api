from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from django.db.models import Count, IntegerField, OuterRef, QuerySet, Subquery, Value
from django.db.models.functions import Coalesce

from core.time.clock import Clock
from features.gallery.domain.trash_rules import TrashedItemKind, purge_order
from features.gallery.dtos.trash_dtos import (
    PurgedBatch,
    TrashedRoot,
    TrashEntryRow,
    TrashOutcome,
)
from features.gallery.models.gallery import Album, Photo
from features.gallery.models.trash import GalleryDeletionBatch


class TrashRepositoryImpl:
    """Deletion batches and the trashed rows they hold. The only repository, with the purge's and
    the media lookup's, that reads ``all_objects`` (specs/014-gallery-trash-sync research R-01)."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock

    def create_batch(self, kind: TrashedItemKind, root_id: int, actor_id: UUID | None) -> UUID:
        """>>> repository.create_batch(TrashedItemKind.PHOTO, 301, user_id)
        UUID('9b1e…')
        """
        batch = GalleryDeletionBatch.objects.create(
            root_kind=kind.value,
            root_id=root_id,
            deleted_at=self._clock.now(),
            deleted_by_id=actor_id,
        )
        return UUID(str(batch.pk))

    def trash_photo(self, photo_id: int, batch_id: UUID) -> bool:
        """Trash one live photo; False when it is gone or already trashed. Locks its album row
        first, so it serializes with a concurrent move of the same photo."""
        album_id = Photo.objects.filter(pk=photo_id).values_list("album_id", flat=True).first()
        if album_id is None:
            return False
        list(Album.objects.select_for_update().filter(pk=album_id).values_list("pk"))
        return bool(Photo.objects.filter(pk=photo_id).update(**self._trash_fields(batch_id)))

    def trash_albums(self, album_ids: Sequence[int], batch_id: UUID) -> list[int]:
        """Trash the live albums among ``album_ids``; returns those actually trashed."""
        live = list(Album.objects.filter(pk__in=album_ids).values_list("id", flat=True))
        Album.objects.filter(pk__in=live).update(**self._trash_fields(batch_id))
        return sorted(live)

    def trash_photos_of_albums(self, album_ids: Sequence[int], batch_id: UUID) -> list[int]:
        """Trash the live photos of those albums; photos trashed earlier keep their batch."""
        live = list(Photo.objects.filter(album_id__in=album_ids).values_list("id", flat=True))
        Photo.objects.filter(pk__in=live).update(**self._trash_fields(batch_id))
        return sorted(live)

    def batch_rooted_at(self, kind: TrashedItemKind, root_id: int) -> TrashedRoot | None:
        """The batch whose root is this item, while it is in the trash; None otherwise."""
        batch = GalleryDeletionBatch.objects.filter(root_kind=kind.value, root_id=root_id).first()
        if batch is None:
            return None
        return _root_of(batch, kind, root_id)

    def restore_batch(self, batch_id: UUID) -> TrashOutcome:
        """Make every row of the batch live again and drop the batch. Positions are kept."""
        batch = GalleryDeletionBatch.objects.get(pk=batch_id)
        album_ids = sorted(
            Album.all_objects.filter(deletion_batch=batch).values_list("id", flat=True)
        )
        photo_ids = sorted(
            Photo.all_objects.filter(deletion_batch=batch).values_list("id", flat=True)
        )
        live = {"deleted_at": None, "deletion_batch": None, "updated_at": self._clock.now()}
        Photo.all_objects.filter(pk__in=photo_ids).update(**live)
        Album.all_objects.filter(pk__in=album_ids).update(**live)
        batch.delete()
        return TrashOutcome(
            batch_id=batch_id,
            kind=TrashedItemKind(batch.root_kind),
            root_id=batch.root_id,
            album_ids=album_ids,
            photo_ids=photo_ids,
        )

    def list_entries(self) -> list[TrashEntryRow]:
        """One row per batch, most recent first, in four queries (research R-13)."""
        batches = list(_batches_with_counts())
        albums = Album.all_objects.in_bulk(_root_ids(batches, TrashedItemKind.ALBUM))
        photos = Photo.all_objects.select_related("uploaded_by").in_bulk(
            _root_ids(batches, TrashedItemKind.PHOTO)
        )
        rows = (_entry_row(batch, albums, photos) for batch in batches)
        return [row for row in rows if row is not None]

    def expired_batch_ids(self, before: datetime) -> list[UUID]:
        """Batches deleted before ``before``, oldest first, so a descendant trashed on its own
        is purged before its parent's later batch."""
        batches = GalleryDeletionBatch.objects.filter(deleted_at__lt=before)
        return [
            UUID(str(pk))
            for pk in batches.order_by("deleted_at", "id").values_list("pk", flat=True)
        ]

    def purge_batch(self, batch_id: UUID) -> PurgedBatch:
        """Delete the batch's rows for good (photos, albums deepest first, the batch) and return
        the file names to remove once the caller's transaction commits."""
        photos = Photo.all_objects.filter(deletion_batch_id=batch_id)
        albums = Album.all_objects.filter(deletion_batch_id=batch_id)
        purged = PurgedBatch(
            album_ids=sorted(albums.values_list("id", flat=True)),
            photo_ids=sorted(photos.values_list("id", flat=True)),
            file_names=_file_names(photos, albums),
        )
        photos.delete()
        parent_of = dict(albums.values_list("id", "parent_id"))
        for album_id in purge_order(purged.album_ids, parent_of):
            Album.all_objects.filter(pk=album_id).delete()
        GalleryDeletionBatch.objects.filter(pk=batch_id).delete()
        return purged

    def _trash_fields(self, batch_id: UUID) -> dict[str, Any]:
        now = self._clock.now()
        return {"deleted_at": now, "deletion_batch_id": batch_id, "updated_at": now}


def _root_of(
    batch: GalleryDeletionBatch, kind: TrashedItemKind, root_id: int
) -> TrashedRoot | None:
    if kind is TrashedItemKind.ALBUM:
        row = Album.all_objects.filter(pk=root_id).values_list("name", "parent_id").first()
    else:
        row = Photo.all_objects.filter(pk=root_id).values_list("name", "album_id").first()
    if row is None:
        return None
    return TrashedRoot(
        batch_id=UUID(str(batch.pk)),
        kind=kind,
        root_id=root_id,
        name=row[0],
        parent_album_id=row[1],
    )


def _count_in_batch(rows: QuerySet[Any]) -> Coalesce:
    counted = (
        rows.filter(deletion_batch=OuterRef("pk")).values("deletion_batch").annotate(n=Count("id"))
    )
    return Coalesce(Subquery(counted.values("n"), output_field=IntegerField()), Value(0))


def _batches_with_counts() -> QuerySet[GalleryDeletionBatch]:
    return (
        GalleryDeletionBatch.objects.select_related("deleted_by")
        .annotate(
            album_count=_count_in_batch(Album.all_objects.all()),
            photo_count=_count_in_batch(Photo.all_objects.all()),
        )
        .order_by("-deleted_at", "id")
    )


def _root_ids(batches: Sequence[GalleryDeletionBatch], kind: TrashedItemKind) -> list[int]:
    return [batch.root_id for batch in batches if batch.root_kind == kind.value]


def _display_name(user: Any) -> str | None:
    if user is None:
        return None
    return str(user.get_full_name() or user.username)


def _entry_row(
    batch: Any, albums: dict[int, Album], photos: dict[int, Photo]
) -> TrashEntryRow | None:
    if batch.root_kind == TrashedItemKind.ALBUM.value:
        album = albums.get(batch.root_id)
        return _album_entry(batch, album) if album is not None else None
    photo = photos.get(batch.root_id)
    return _photo_entry(batch, photo) if photo is not None else None


def _album_entry(batch: Any, album: Album) -> TrashEntryRow:
    return TrashEntryRow(
        kind=TrashedItemKind.ALBUM,
        id=album.pk,
        name=album.name,
        deleted_at=batch.deleted_at,
        deleted_by=_display_name(batch.deleted_by),
        uploaded_by=None,
        # The root album is counted in its own batch; the entry reports what went with it.
        sub_album_count=batch.album_count - 1,
        photo_count=batch.photo_count,
        thumbnail_name=album.cover_image.name or None,
    )


def _photo_entry(batch: Any, photo: Photo) -> TrashEntryRow:
    return TrashEntryRow(
        kind=TrashedItemKind.PHOTO,
        id=photo.pk,
        name=photo.name,
        deleted_at=batch.deleted_at,
        deleted_by=_display_name(batch.deleted_by),
        uploaded_by=_display_name(photo.uploaded_by),
        sub_album_count=0,
        photo_count=0,
        thumbnail_name=photo.thumbnail.name or None,
    )


def _file_names(photos: QuerySet[Photo], albums: QuerySet[Album]) -> list[str]:
    names = [name for pair in photos.values_list("image", "thumbnail") for name in pair]
    names.extend(albums.values_list("cover_image", flat=True))
    return sorted(name for name in names if name)
