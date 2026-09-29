from datetime import datetime

from core.time.clock import Clock
from features.gallery.domain.feed_cursor import (
    decode_cursor,
    encode_cursor,
    feed_window_start,
    requires_full_sync,
)
from features.gallery.domain.trash_rules import TrashedItemKind
from features.gallery.dtos.feed_dtos import ChangeFeed
from features.gallery.repositories.interfaces import (
    AlbumRepository,
    DeletionMarkRepository,
    GalleryRepository,
)
from features.gallery.services.album_service import AlbumService
from features.gallery.services.photo_ordering import order_photos_by_tree


class GalleryChangeFeedService:
    """What changed in the gallery since a cursor, so the app syncs only that and drops what was
    deleted (specs/014-gallery-trash-sync research R-07).

    The new cursor is the instant the read starts, taken before any query, and every delta
    re-covers ``CURSOR_OVERLAP`` before its cursor: a change that commits late is returned twice
    at worst, never missed.
    """

    def __init__(
        self,
        album_service: AlbumService,
        album_repository: AlbumRepository,
        gallery_repository: GalleryRepository,
        mark_repository: DeletionMarkRepository,
        clock: Clock,
    ) -> None:
        self._album_views = album_service
        self._albums = album_repository
        self._photos = gallery_repository
        self._marks = mark_repository
        self._clock = clock

    def changes(self, since_raw: str | None) -> ChangeFeed:
        """Full sync without a cursor, a delta with a readable recent one, and
        ``full_sync_required`` for anything else.

        >>> service.changes(None).full_sync_required
        False
        """
        now = self._clock.now()
        cursor = encode_cursor(now)
        if since_raw is None:
            return self._full_sync(cursor)
        since = decode_cursor(since_raw)
        if since is None or requires_full_sync(since, now):
            return _empty(cursor, full_sync_required=True)
        return self._delta(feed_window_start(since), cursor)

    def _full_sync(self, cursor: str) -> ChangeFeed:
        photos = order_photos_by_tree(self._photos.list_all_photos(), self._albums.list_records())
        return ChangeFeed(
            albums=self._album_views.list_albums(),
            photos=photos,
            deleted_album_ids=[],
            deleted_photo_ids=[],
            cursor=cursor,
            full_sync_required=False,
        )

    def _delta(self, start: datetime, cursor: str) -> ChangeFeed:
        albums = [a for a in self._album_views.list_albums() if a.updated_at > start]
        changed = self._photos.list_photos_changed_since(start)
        return ChangeFeed(
            albums=albums,
            photos=order_photos_by_tree(changed, self._albums.list_records()),
            deleted_album_ids=self._marks.ids_since(TrashedItemKind.ALBUM, start),
            deleted_photo_ids=self._marks.ids_since(TrashedItemKind.PHOTO, start),
            cursor=cursor,
            full_sync_required=False,
        )


def _empty(cursor: str, full_sync_required: bool) -> ChangeFeed:
    return ChangeFeed(
        albums=[],
        photos=[],
        deleted_album_ids=[],
        deleted_photo_ids=[],
        cursor=cursor,
        full_sync_required=full_sync_required,
    )
