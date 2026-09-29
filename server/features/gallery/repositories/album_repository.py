from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager

from django.db import IntegrityError, transaction
from django.db.models import Max, QuerySet

from core.domain.exceptions import AlbumNotFoundError, DuplicateAlbumNameError
from core.time.clock import Clock
from features.gallery.dtos.gallery_dtos import AlbumCreate, AlbumRecord
from features.gallery.models.gallery import Album, Photo

_RECORD_FIELDS = (
    "id",
    "name",
    "parent_id",
    "description",
    "event_date",
    "position",
    "cover_image",
    "updated_at",
)


class AlbumRepositoryImpl:
    """Live albums through the Django ORM (``Album.objects`` hides trashed rows).

    Every write sets ``updated_at`` from the injected clock, which the change feed reads
    (specs/014-gallery-trash-sync research R-06).
    """

    def __init__(self, clock: Clock) -> None:
        self._clock = clock

    def exists(self, album_id: int) -> bool:
        return Album.objects.filter(pk=album_id).exists()

    def get_record(self, album_id: int) -> AlbumRecord | None:
        row = Album.objects.filter(pk=album_id).values(*_RECORD_FIELDS).first()
        return _to_record(row) if row else None

    def list_records(self) -> list[AlbumRecord]:
        return [_to_record(row) for row in Album.objects.values(*_RECORD_FIELDS)]

    def sibling_name_taken(self, name: str, parent_id: int | None, exclude_id: int | None) -> bool:
        same_name = _siblings(parent_id).filter(name=name)
        if exclude_id is not None:
            same_name = same_name.exclude(pk=exclude_id)
        return same_name.exists()

    def live_sibling_named(self, name: str, parent_id: int | None) -> int | None:
        """Id of the live album holding ``name`` under ``parent_id``, or None.

        >>> repository.live_sibling_named("Culto", 2)
        12
        """
        return _siblings(parent_id).filter(name=name).values_list("id", flat=True).first()

    def parent_map(self, lock: bool) -> dict[int, int | None]:
        """Every live album's parent in one query; ``lock`` holds every album row until commit,
        so two concurrent moves cannot build a cycle together (013 research R-02)."""
        albums = Album.objects.select_for_update() if lock else Album.objects.all()
        return dict(albums.values_list("id", "parent_id"))

    def next_position(self, parent_id: int | None) -> int:
        """Position after the last sibling; locks the parent row so appends serialize."""
        if parent_id is not None:
            _lock_live_album(parent_id)
        last = _siblings(parent_id).aggregate(last=Max("position"))["last"]
        return 0 if last is None else last + 1

    def create(self, album: AlbumCreate, position: int) -> int:
        with _translate_duplicate(album.name, album.parent_id):
            created = Album.objects.create(
                **album.model_dump(), position=position, updated_at=self._clock.now()
            )
        return int(created.pk)

    def update(self, album_id: int, fields: Mapping[str, object]) -> None:
        name = str(fields.get("name", ""))
        with _translate_duplicate(name, _int_or_none(fields.get("parent_id"))):
            Album.objects.filter(pk=album_id).update(**fields, updated_at=self._clock.now())

    def child_ids(self, parent_id: int | None) -> list[int]:
        return list(_siblings(parent_id).values_list("id", flat=True))

    def apply_order(self, ids: Sequence[int]) -> None:
        """Write the new positions of the rows that actually move, and only those, so the feed
        reports exactly the albums whose ``position`` changed."""
        current = dict(Album.objects.filter(pk__in=ids).values_list("id", "position"))
        now = self._clock.now()
        moved = [
            Album(pk=album_id, position=index, updated_at=now)
            for index, album_id in enumerate(ids)
            if current.get(album_id) != index
        ]
        with transaction.atomic():
            Album.objects.bulk_update(moved, ["position", "updated_at"])

    def has_photos(self, album_id: int) -> bool:
        return Photo.objects.filter(album_id=album_id).exists()

    def set_cover_name(self, album_id: int, name: str | None) -> None:
        Album.objects.filter(pk=album_id).update(
            cover_image=name or "", updated_at=self._clock.now()
        )

    def set_cover_name_if_absent(self, album_id: int, name: str) -> bool:
        """Set the cover only if the album still has none; False when another write won."""
        changed = Album.objects.filter(pk=album_id, cover_image="").update(
            cover_image=name, updated_at=self._clock.now()
        )
        return bool(changed)

    def touch(self, ids: Sequence[int]) -> None:
        """Mark live albums as changed, e.g. when their resolved cover changed.

        >>> repository.touch([2, 7])
        """
        if ids:
            Album.objects.filter(pk__in=ids).update(updated_at=self._clock.now())

    def touch_photos_of(self, album_id: int) -> None:
        """Mark the live photos of an album as changed: their ``album_name`` follows a rename.

        >>> repository.touch_photos_of(7)
        """
        Photo.objects.filter(album_id=album_id).update(updated_at=self._clock.now())


def _lock_live_album(album_id: int) -> None:
    """Lock a live album row, or raise. A lock taken through the live manager re-checks
    ``deleted_at`` after waiting, so an album trashed meanwhile yields no row: without this check a
    photo or album would be placed under a trashed album (specs/014 research R-02)."""
    locked = Album.objects.select_for_update().filter(pk=album_id).values_list("pk", flat=True)
    if not list(locked):
        raise AlbumNotFoundError(album_id)


def _siblings(parent_id: int | None) -> QuerySet[Album]:
    if parent_id is None:
        return Album.objects.filter(parent__isnull=True)
    return Album.objects.filter(parent_id=parent_id)


def _to_record(row: Mapping[str, object]) -> AlbumRecord:
    values = dict(row)
    values["cover_name"] = values.pop("cover_image") or ""
    return AlbumRecord.model_validate(values)


def _int_or_none(value: object) -> int | None:
    return value if isinstance(value, int) else None


# PostgreSQL names the constraint; SQLite names the columns of the unique index instead.
_DUPLICATE_NAME_MARKERS = (
    "unique_live_album_name_per_parent",
    "unique_live_root_album_name",
    "gallery_album.name",
)


@contextmanager
def _translate_duplicate(name: str, parent_id: int | None) -> Iterator[None]:
    """The unique constraints catch what the service pre-check cannot: a concurrent write."""
    try:
        with transaction.atomic():
            yield
    except IntegrityError as exc:
        if any(marker in str(exc) for marker in _DUPLICATE_NAME_MARKERS):
            raise DuplicateAlbumNameError(name, parent_id) from exc
        raise
