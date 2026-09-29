from collections.abc import Sequence

from django.db import transaction

from core.domain.exceptions import AlbumCycleError, AlbumNotFoundError, DuplicateAlbumNameError
from features.gallery.domain.album_tree import (
    AlbumNode,
    find_cycle,
    resolve_cover_sources,
    tree_order,
)
from features.gallery.domain.gallery_rules import normalize_album_name
from features.gallery.dtos.gallery_dtos import (
    AlbumChanges,
    AlbumCreate,
    AlbumRecord,
    AlbumView,
    SiblingOrder,
)
from features.gallery.repositories.interfaces import AlbumRepository, GalleryFileStorage
from features.gallery.services.cover_change_tracker import CoverChangeTracker
from features.gallery.services.ordering import ensure_exact_order

_PLAIN_FIELDS = ("description", "event_date")


class AlbumService:
    """Albums: the tree, names, order and the resolved cover members see.

    Tree mutations hold every album row locked (``parent_map(lock=True)``) while they check and
    write, so concurrent moves cannot combine into a cycle (specs/013-gallery-write-api R-02).
    """

    def __init__(
        self,
        album_repository: AlbumRepository,
        file_storage: GalleryFileStorage,
        cover_tracker: CoverChangeTracker,
    ) -> None:
        self._albums = album_repository
        self._storage = file_storage
        self._covers = cover_tracker

    def list_albums(self) -> list[AlbumView]:
        """Every album, empty ones included, in tree order.

        >>> [album.name for album in service.list_albums()]
        ['Retiros', '2026', 'Cultos']
        """
        records = self._albums.list_records()
        views = self._build_views(records)
        return [views[album_id] for album_id in tree_order(_nodes(records))]

    def view_of(self, album_id: int) -> AlbumView:
        """>>> service.view_of(7).cover_source_album_id
        9
        """
        views = self._build_views(self._albums.list_records())
        if album_id not in views:
            raise AlbumNotFoundError(album_id)
        return views[album_id]

    def create(self, album: AlbumCreate) -> AlbumView:
        """Create an album last among its siblings.

        >>> service.create(AlbumCreate(name="Retiro 2026", parent_id=2)).parent_id
        2
        """
        name = normalize_album_name(album.name)
        with transaction.atomic():
            self._require_parent(album.parent_id)
            self._require_free_name(name, album.parent_id, exclude_id=None)
            position = self._albums.next_position(album.parent_id)
            album_id = self._albums.create(album.model_copy(update={"name": name}), position)
        return self.view_of(album_id)

    def update(self, album_id: int, changes: AlbumChanges) -> AlbumView:
        """Rename, move (``parent_id`` sent; ``None`` = root) or edit the optional fields.

        >>> service.update(3, AlbumChanges(parent_id=None)).parent_id is None
        True
        """
        with transaction.atomic():
            current = self._require_record(album_id)
            fields = self._placement_fields(current, changes)
            fields.update(
                {
                    key: getattr(changes, key)
                    for key in _PLAIN_FIELDS
                    if key in changes.model_fields_set
                }
            )
            if fields:
                self._write_update(current, fields)
        return self.view_of(album_id)

    def _write_update(self, current: AlbumRecord, fields: dict[str, object]) -> None:
        """Write the change and mark what it changed for the feed: a move can change the
        resolved cover of old and new ancestors, a rename the ``album_name`` of every photo."""
        moved = fields.get("parent_id", current.parent_id) != current.parent_id
        before = self._covers.snapshot() if moved else None
        self._albums.update(current.id, fields)
        if before is not None:
            self._covers.touch_changed(before)
        if fields.get("name", current.name) != current.name:
            self._albums.touch_photos_of(current.id)

    def validate_placement(self, album_id: int | None, name: str, parent_id: int | None) -> None:
        """Every rule a create or edit must pass, for callers that save by themselves (the Django
        admin form). Raises the same domain errors as ``create`` / ``update``.

        >>> service.validate_placement(3, "Retiros", 9)
        """
        clean_name = normalize_album_name(name)
        with transaction.atomic():
            self._require_parent(parent_id)
            if album_id is not None:
                self._require_no_cycle(album_id, parent_id)
            self._require_free_name(clean_name, parent_id, exclude_id=album_id)

    def reorder(self, order: SiblingOrder) -> None:
        """Replace the order of the children of ``order.parent_id`` (roots when None).

        >>> service.reorder(SiblingOrder(parent_id=None, ids=[5, 1, 3]))
        """
        with transaction.atomic():
            self._require_parent(order.parent_id)
            ensure_exact_order(order.ids, self._albums.child_ids(order.parent_id))
            # A new first child can change which cover the parent and its ancestors inherit.
            before = self._covers.snapshot()
            self._albums.apply_order(order.ids)
            self._covers.touch_changed(before)

    def _placement_fields(self, current: AlbumRecord, changes: AlbumChanges) -> dict[str, object]:
        """``name``, ``parent_id`` and ``position`` to write, after checking the new place."""
        sent = changes.model_fields_set
        name = normalize_album_name(changes.name or "") if "name" in sent else current.name
        parent_id = changes.parent_id if "parent_id" in sent else current.parent_id
        moved = parent_id != current.parent_id
        if name == current.name and not moved:
            return {}
        if moved:
            self._require_parent(parent_id)
            self._require_no_cycle(current.id, parent_id)
        self._require_free_name(name, parent_id, exclude_id=current.id)
        fields: dict[str, object] = {"name": name, "parent_id": parent_id}
        if moved:
            fields["position"] = self._albums.next_position(parent_id)
        return fields

    def _require_record(self, album_id: int) -> AlbumRecord:
        record = self._albums.get_record(album_id)
        if record is None:
            raise AlbumNotFoundError(album_id)
        return record

    def _require_parent(self, parent_id: int | None) -> None:
        if parent_id is not None and not self._albums.exists(parent_id):
            raise AlbumNotFoundError(parent_id)

    def _require_no_cycle(self, album_id: int, parent_id: int | None) -> None:
        chain = find_cycle(album_id, parent_id, self._albums.parent_map(lock=True))
        if chain is not None and parent_id is not None:
            raise AlbumCycleError(album_id, parent_id, chain)

    def _require_free_name(self, name: str, parent_id: int | None, exclude_id: int | None) -> None:
        if self._albums.sibling_name_taken(name, parent_id, exclude_id):
            raise DuplicateAlbumNameError(name, parent_id)

    def _build_views(self, records: Sequence[AlbumRecord]) -> dict[int, AlbumView]:
        sources = resolve_cover_sources(_nodes(records))
        cover_names = {record.id: record.cover_name for record in records}
        return {
            record.id: self._view(record, sources[record.id], cover_names) for record in records
        }

    def _view(
        self, record: AlbumRecord, source: int | None, cover_names: dict[int, str]
    ) -> AlbumView:
        return AlbumView(
            id=record.id,
            name=record.name,
            parent_id=record.parent_id,
            description=record.description,
            event_date=record.event_date,
            cover_path=self._storage.url(cover_names[source]) if source is not None else None,
            cover_source_album_id=source,
            position=record.position,
            updated_at=record.updated_at,
        )


def _nodes(records: Sequence[AlbumRecord]) -> list[AlbumNode]:
    return [
        AlbumNode(record.id, record.parent_id, record.position, bool(record.cover_name))
        for record in records
    ]
