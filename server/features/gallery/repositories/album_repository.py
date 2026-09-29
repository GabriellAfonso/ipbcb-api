from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager

from django.db import IntegrityError, transaction
from django.db.models import Max, QuerySet

from core.domain.exceptions import DuplicateAlbumNameError
from features.gallery.dtos.gallery_dtos import AlbumCreate, AlbumRecord
from features.gallery.models.gallery import Album, Photo

_RECORD_FIELDS = ("id", "name", "parent_id", "description", "event_date", "position", "cover_image")


class AlbumRepositoryImpl:
    """Albums through the Django ORM."""

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

    def parent_map(self, lock: bool) -> dict[int, int | None]:
        """Every album's parent in one query; ``lock`` holds every album row until commit, so
        two concurrent moves cannot build a cycle together (research R-02)."""
        albums = Album.objects.select_for_update() if lock else Album.objects.all()
        return dict(albums.values_list("id", "parent_id"))

    def next_position(self, parent_id: int | None) -> int:
        """Position after the last sibling; locks the parent row so appends serialize."""
        if parent_id is not None:
            list(Album.objects.select_for_update().filter(pk=parent_id).values_list("pk"))
        last = _siblings(parent_id).aggregate(last=Max("position"))["last"]
        return 0 if last is None else last + 1

    def create(self, album: AlbumCreate, position: int) -> int:
        with _translate_duplicate(album.name, album.parent_id):
            created = Album.objects.create(**album.model_dump(), position=position)
        return int(created.pk)

    def update(self, album_id: int, fields: Mapping[str, object]) -> None:
        name = str(fields.get("name", ""))
        with _translate_duplicate(name, _int_or_none(fields.get("parent_id"))):
            Album.objects.filter(pk=album_id).update(**fields)

    def child_ids(self, parent_id: int | None) -> list[int]:
        return list(_siblings(parent_id).values_list("id", flat=True))

    def apply_order(self, ids: Sequence[int]) -> None:
        albums = [Album(pk=album_id, position=index) for index, album_id in enumerate(ids)]
        with transaction.atomic():
            Album.objects.bulk_update(albums, ["position"])

    def has_photos(self, album_id: int) -> bool:
        return Photo.objects.filter(album_id=album_id).exists()

    def set_cover_name(self, album_id: int, name: str | None) -> None:
        Album.objects.filter(pk=album_id).update(cover_image=name or "")

    def set_cover_name_if_absent(self, album_id: int, name: str) -> bool:
        """Set the cover only if the album still has none; False when another write won."""
        return bool(Album.objects.filter(pk=album_id, cover_image="").update(cover_image=name))


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
    "unique_album_name_per_parent",
    "unique_root_album_name",
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
