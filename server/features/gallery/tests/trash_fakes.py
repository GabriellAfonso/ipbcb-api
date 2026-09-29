"""Named fakes for the trash repositories (CLAUDE.md §10), over the album and photo fakes of
``features.gallery.tests.fakes`` (specs/014-gallery-trash-sync)."""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID, uuid4

from features.gallery.domain.trash_rules import TrashedItemKind
from features.gallery.dtos.trash_dtos import (
    PurgedBatch,
    TrashedRoot,
    TrashEntryRow,
    TrashOutcome,
)
from features.gallery.tests.fakes import FakeAlbumRepository, FakeClock, FakeGalleryRepository


class FakeTrashRepository:
    """Batches over the rows of the album and photo fakes: trashing moves a row from ``records``
    / ``photos`` to their ``trashed`` dict, restoring moves it back."""

    def __init__(self, albums: FakeAlbumRepository, photos: FakeGalleryRepository) -> None:
        self.albums = albums
        self.photos = photos
        self.batches: dict[UUID, tuple[TrashedItemKind, int, UUID | None, datetime]] = {}
        self.album_batch: dict[int, UUID] = {}
        self.photo_batch: dict[int, UUID] = {}
        self.purged: list[UUID] = []
        self.failing_batches: set[UUID] = set()

    def create_batch(self, kind: TrashedItemKind, root_id: int, actor_id: UUID | None) -> UUID:
        batch_id = uuid4()
        self.batches[batch_id] = (kind, root_id, actor_id, self.albums.clock.now())
        return batch_id

    def trash_photo(self, photo_id: int, batch_id: UUID) -> bool:
        if photo_id not in self.photos.photos:
            return False
        self._trash_photo(photo_id, batch_id)
        return True

    def trash_albums(self, album_ids: Sequence[int], batch_id: UUID) -> list[int]:
        live = sorted(i for i in album_ids if i in self.albums.records)
        for album_id in live:
            self.albums.trashed[album_id] = self.albums.records.pop(album_id)
            self.album_batch[album_id] = batch_id
        return live

    def trash_photos_of_albums(self, album_ids: Sequence[int], batch_id: UUID) -> list[int]:
        live = sorted(p.id for p in self.photos.photos.values() if p.album_id in album_ids)
        for photo_id in live:
            self._trash_photo(photo_id, batch_id)
        return live

    def batch_rooted_at(self, kind: TrashedItemKind, root_id: int) -> TrashedRoot | None:
        for batch_id, (batch_kind, batch_root, _, _) in self.batches.items():
            if (batch_kind, batch_root) == (kind, root_id):
                return self._root(batch_id, kind, root_id)
        return None

    def restore_batch(self, batch_id: UUID) -> TrashOutcome:
        kind, root_id, _, _ = self.batches.pop(batch_id)
        album_ids = sorted(i for i, b in self.album_batch.items() if b == batch_id)
        photo_ids = sorted(i for i, b in self.photo_batch.items() if b == batch_id)
        for album_id in album_ids:
            del self.album_batch[album_id]
            self.albums.records[album_id] = self.albums.trashed.pop(album_id)
            self.albums.update(album_id, {})
        for photo_id in photo_ids:
            del self.photo_batch[photo_id]
            self.photos.photos[photo_id] = self.photos.trashed.pop(photo_id)
            self.photos.update_photo(photo_id, {})
        return TrashOutcome(
            batch_id=batch_id, kind=kind, root_id=root_id, album_ids=album_ids, photo_ids=photo_ids
        )

    def list_entries(self) -> list[TrashEntryRow]:
        ordered = sorted(self.batches.items(), key=lambda item: item[1][3], reverse=True)
        return [self._row(batch_id, *values) for batch_id, values in ordered]

    def expired_batch_ids(self, before: datetime) -> list[UUID]:
        old = [
            (values[3], batch_id) for batch_id, values in self.batches.items() if values[3] < before
        ]
        return [batch_id for _, batch_id in sorted(old, key=lambda item: item[0])]

    def purge_batch(self, batch_id: UUID) -> PurgedBatch:
        if batch_id in self.failing_batches:
            raise RuntimeError(f"cannot purge {batch_id}")
        album_ids = sorted(i for i, b in self.album_batch.items() if b == batch_id)
        photo_ids = sorted(i for i, b in self.photo_batch.items() if b == batch_id)
        names = [self.photos.images[i] for i in photo_ids]
        names += [self.photos.thumbnails[i] for i in photo_ids if self.photos.thumbnails[i]]
        names += [
            self.albums.trashed[i].cover_name
            for i in album_ids
            if self.albums.trashed[i].cover_name
        ]
        for album_id in album_ids:
            del self.album_batch[album_id], self.albums.trashed[album_id]
        for photo_id in photo_ids:
            del self.photo_batch[photo_id], self.photos.trashed[photo_id]
        del self.batches[batch_id]
        self.purged.append(batch_id)
        return PurgedBatch(album_ids=album_ids, photo_ids=photo_ids, file_names=sorted(names))

    def _trash_photo(self, photo_id: int, batch_id: UUID) -> None:
        self.photos.trashed[photo_id] = self.photos.photos.pop(photo_id)
        self.photo_batch[photo_id] = batch_id

    def _root(self, batch_id: UUID, kind: TrashedItemKind, root_id: int) -> TrashedRoot:
        if kind is TrashedItemKind.ALBUM:
            album = self.albums.trashed[root_id]
            name, parent = album.name, album.parent_id
        else:
            photo = self.photos.trashed[root_id]
            name, parent = photo.name, photo.album_id
        return TrashedRoot(
            batch_id=batch_id, kind=kind, root_id=root_id, name=name, parent_album_id=parent
        )

    def _row(
        self,
        batch_id: UUID,
        kind: TrashedItemKind,
        root_id: int,
        actor_id: UUID | None,
        deleted_at: datetime,
    ) -> TrashEntryRow:
        albums = sum(1 for b in self.album_batch.values() if b == batch_id)
        photos = sum(1 for b in self.photo_batch.values() if b == batch_id)
        is_album = kind is TrashedItemKind.ALBUM
        root_name = (
            self.albums.trashed[root_id].name if is_album else self.photos.trashed[root_id].name
        )
        return TrashEntryRow(
            kind=kind,
            id=root_id,
            name=root_name,
            deleted_at=deleted_at,
            deleted_by=str(actor_id) if actor_id else None,
            uploaded_by=None,
            sub_album_count=albums - 1 if is_album else 0,
            photo_count=photos if is_album else 0,
            thumbnail_name=None,
        )


class FakeDeletionMarkRepository:
    """Marks in a dict keyed by (kind, id), dated by the shared clock."""

    def __init__(self, clock: FakeClock) -> None:
        self.clock = clock
        self.marks: dict[tuple[TrashedItemKind, int], datetime] = {}

    def upsert(self, kind: TrashedItemKind, ids: Sequence[int]) -> None:
        for item_id in ids:
            self.marks[(kind, item_id)] = self.clock.now()

    def remove(self, kind: TrashedItemKind, ids: Sequence[int]) -> None:
        for item_id in ids:
            self.marks.pop((kind, item_id), None)

    def ids_since(self, kind: TrashedItemKind, since: datetime) -> list[int]:
        return sorted(i for (k, i), at in self.marks.items() if k is kind and at > since)

    def expire(self, before: datetime) -> int:
        old = [key for key, at in self.marks.items() if at < before]
        for key in old:
            del self.marks[key]
        return len(old)
