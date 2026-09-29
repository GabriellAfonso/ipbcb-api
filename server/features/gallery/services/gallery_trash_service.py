import logging
from uuid import UUID

from django.db import IntegrityError, transaction

from core.domain.exceptions import (
    AlbumNotFoundError,
    AlbumRestoreNameConflictError,
    PhotoNotFoundError,
    TrashedParentError,
    TrashEntryNotFoundError,
)
from features.gallery.domain.trash_rules import TrashedItemKind, purge_on, subtree_ids
from features.gallery.dtos.gallery_dtos import AlbumView, PhotoView
from features.gallery.dtos.trash_dtos import TrashedRoot, TrashEntry, TrashEntryRow, TrashOutcome
from features.gallery.repositories.interfaces import (
    AlbumRepository,
    DeletionMarkRepository,
    GalleryFileStorage,
    GalleryRepository,
    TrashRepository,
)
from features.gallery.services.album_service import AlbumService
from features.gallery.services.cover_change_tracker import CoverChangeTracker

logger = logging.getLogger("features.gallery")

ALBUM = TrashedItemKind.ALBUM
PHOTO = TrashedItemKind.PHOTO


class GalleryTrashService:
    """Deleting to the trash, listing it, and restoring from it.

    Tree-affecting steps hold every live album row locked (``parent_map(lock=True)``), like the
    013 moves, so a delete or restore cannot interleave with a move, a create or an upload under
    the same subtree (specs/014-gallery-trash-sync research R-03, R-04).
    """

    def __init__(
        self,
        album_repository: AlbumRepository,
        gallery_repository: GalleryRepository,
        trash_repository: TrashRepository,
        mark_repository: DeletionMarkRepository,
        cover_tracker: CoverChangeTracker,
        album_service: AlbumService,
        file_storage: GalleryFileStorage,
    ) -> None:
        self._albums = album_repository
        self._photos = gallery_repository
        self._trash = trash_repository
        self._marks = mark_repository
        self._covers = cover_tracker
        self._album_views = album_service
        self._storage = file_storage

    def delete_photo(self, photo_id: int, actor_id: UUID | None) -> TrashOutcome:
        """Send one live photo to the trash, in a batch of its own.

        >>> service.delete_photo(301, user_id).photo_ids
        [301]
        """
        with transaction.atomic():
            if self._photos.get_photo(photo_id) is None:
                raise PhotoNotFoundError(photo_id)
            batch_id = self._trash.create_batch(PHOTO, photo_id, actor_id)
            if not self._trash.trash_photo(photo_id, batch_id):
                raise PhotoNotFoundError(photo_id)  # a concurrent delete won
            self._marks.upsert(PHOTO, [photo_id])
        outcome = TrashOutcome(
            batch_id=batch_id, kind=PHOTO, root_id=photo_id, album_ids=[], photo_ids=[photo_id]
        )
        _log("gallery_trashed", outcome, actor_id)
        return outcome

    def delete_album(self, album_id: int, actor_id: UUID | None) -> TrashOutcome:
        """Send a live album, its live descendants and all their live photos to the trash, in
        one batch. Items already trashed keep their own batch.

        >>> service.delete_album(7, user_id).album_ids
        [7, 9]
        """
        with transaction.atomic():
            parent_of = self._albums.parent_map(lock=True)
            if album_id not in parent_of:
                raise AlbumNotFoundError(album_id)
            before = self._covers.snapshot()
            outcome = self._trash_subtree(album_id, subtree_ids(album_id, parent_of), actor_id)
            self._covers.touch_changed(before)
        _log("gallery_trashed", outcome, actor_id)
        return outcome

    def list_trash(self) -> list[TrashEntry]:
        """One entry per deletion batch, most recent first.

        >>> service.list_trash()[0].sub_album_count
        2
        """
        return [self._entry(row) for row in self._trash.list_entries()]

    def restore_album(self, album_id: int) -> AlbumView:
        """Restore exactly the batch rooted at this album.

        >>> service.restore_album(7).id
        7
        """
        self._restore(ALBUM, album_id)
        return self._album_views.view_of(album_id)

    def restore_photo(self, photo_id: int) -> PhotoView:
        """Restore a photo that was deleted on its own.

        >>> service.restore_photo(301).album_id
        7
        """
        self._restore(PHOTO, photo_id)
        photo = self._photos.get_photo(photo_id)
        if photo is None:
            raise PhotoNotFoundError(photo_id)
        return photo

    def _trash_subtree(
        self, root_id: int, album_ids: list[int], actor_id: UUID | None
    ) -> TrashOutcome:
        batch_id = self._trash.create_batch(ALBUM, root_id, actor_id)
        trashed_albums = self._trash.trash_albums(album_ids, batch_id)
        trashed_photos = self._trash.trash_photos_of_albums(trashed_albums, batch_id)
        self._marks.upsert(ALBUM, trashed_albums)
        self._marks.upsert(PHOTO, trashed_photos)
        return TrashOutcome(
            batch_id=batch_id,
            kind=ALBUM,
            root_id=root_id,
            album_ids=trashed_albums,
            photo_ids=trashed_photos,
        )

    def _restore(self, kind: TrashedItemKind, item_id: int) -> None:
        with transaction.atomic():
            self._albums.parent_map(lock=True)
            root = self._trash.batch_rooted_at(kind, item_id)
            if root is None:
                raise TrashEntryNotFoundError(kind.value, item_id)
            self._require_restorable(root)
            before = self._covers.snapshot()
            outcome = self._restore_batch(root)
            self._marks.remove(ALBUM, outcome.album_ids)
            self._marks.remove(PHOTO, outcome.photo_ids)
            self._covers.touch_changed(before, also=outcome.album_ids)
        _log("gallery_restored", outcome, None)

    def _require_restorable(self, root: TrashedRoot) -> None:
        parent_id = root.parent_album_id
        if parent_id is not None and not self._albums.exists(parent_id):
            raise TrashedParentError(root.kind.value, root.root_id, parent_id)
        if root.kind is ALBUM:
            self._require_free_name(root)

    def _require_free_name(self, root: TrashedRoot) -> None:
        sibling_id = self._albums.live_sibling_named(root.name, root.parent_album_id)
        if sibling_id is not None:
            raise AlbumRestoreNameConflictError(root.root_id, root.name, sibling_id)

    def _restore_batch(self, root: TrashedRoot) -> TrashOutcome:
        """The unique constraints catch a sibling created concurrently with the check."""
        try:
            with transaction.atomic():
                return self._trash.restore_batch(root.batch_id)
        except IntegrityError as exc:
            sibling_id = self._albums.live_sibling_named(root.name, root.parent_album_id)
            if sibling_id is None:
                raise
            raise AlbumRestoreNameConflictError(root.root_id, root.name, sibling_id) from exc

    def _entry(self, row: TrashEntryRow) -> TrashEntry:
        thumbnail = self._storage.url(row.thumbnail_name) if row.thumbnail_name else None
        return TrashEntry(
            **row.model_dump(exclude={"thumbnail_name"}),
            purge_on=purge_on(row.deleted_at),
            thumbnail_path=thumbnail,
        )


def _log(event: str, outcome: TrashOutcome, actor_id: UUID | None) -> None:
    # Ids and counts only: names and captions never reach the log (research R-14).
    logger.info(
        event,
        extra={
            "kind": outcome.kind.value,
            "id": outcome.root_id,
            "batch": str(outcome.batch_id),
            "actor_id": str(actor_id) if actor_id else None,
            "album_count": len(outcome.album_ids),
            "photo_count": len(outcome.photo_ids),
        },
    )
