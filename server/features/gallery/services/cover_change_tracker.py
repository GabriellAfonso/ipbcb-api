from collections.abc import Mapping, Sequence

from features.gallery.domain.album_tree import AlbumNode, changed_cover_albums, resolved_cover_names
from features.gallery.repositories.interfaces import AlbumRepository


class CoverChangeTracker:
    """Marks as changed exactly the albums whose shown cover a write changed.

    An album's resolved cover can change without its row being written: a descendant's cover was
    replaced, a sub-album was trashed, restored, moved or reordered. The change feed must still
    return that album, so each tree write takes a ``snapshot()`` before and calls
    ``touch_changed`` after, inside the same transaction (specs/014-gallery-trash-sync R-06).
    """

    def __init__(self, album_repository: AlbumRepository) -> None:
        self._albums = album_repository

    def snapshot(self) -> dict[int, str | None]:
        """Resolved cover file name of every live album.

        >>> tracker.snapshot()
        {1: 'gallery/covers/2/a.jpg', 2: 'gallery/covers/2/a.jpg'}
        """
        records = self._albums.list_records()
        nodes = [AlbumNode(r.id, r.parent_id, r.position, bool(r.cover_name)) for r in records]
        return resolved_cover_names(nodes, {r.id: r.cover_name for r in records})

    def touch_changed(
        self, before: Mapping[int, str | None], also: Sequence[int] = ()
    ) -> list[int]:
        """Touch the albums whose resolved cover differs from ``before``, plus ``also``.

        >>> tracker.touch_changed(tracker.snapshot(), also=[7])
        [7]
        """
        changed = changed_cover_albums(before, self.snapshot()) | set(also)
        touched = sorted(changed)
        self._albums.touch(touched)
        return touched
