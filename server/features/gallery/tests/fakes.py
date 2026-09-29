"""Named fakes for the gallery's external I/O (CLAUDE.md §10). Each implements a Protocol from
``features.gallery.imaging.interfaces`` or ``features.gallery.repositories.interfaces``."""

import io
from collections.abc import Iterator, Mapping, Sequence
from datetime import date, datetime, timedelta, timezone
from itertools import count
from typing import IO

from core.domain.exceptions import (
    AlbumNotFoundError,
    DuplicateAlbumNameError,
    ImageProcessingError,
)
from features.gallery.dtos.gallery_dtos import AlbumCreate, AlbumRecord, NewPhoto, PhotoView


def _filename(source: IO[bytes]) -> str:
    return str(getattr(source, "name", "") or "")


class FakeImageProcessor:
    """Returns fixed bytes and records every derivative asked for.

    ``failing_names`` makes derivative calls for those filenames raise like an undecodable
    image; ``size`` is what ``dimensions`` reports.
    """

    THUMBNAIL = b"thumbnail-jpeg"
    COVER = b"cover-jpeg"

    def __init__(
        self,
        size: tuple[int, int] = (4000, 3000),
        taken_on: date | None = None,
        failing_names: frozenset[str] = frozenset(),
    ) -> None:
        self.size = size
        self.taken_on = taken_on
        self.failing_names = failing_names
        self.bounded_calls: list[tuple[str, int, int]] = []
        self.square_calls: list[tuple[str, int, int]] = []

    def dimensions(self, source: IO[bytes]) -> tuple[int, int]:
        return self.size

    def bounded_jpeg(self, source: IO[bytes], longest_side: int, quality: int) -> bytes:
        self._fail_if_asked(source)
        self.bounded_calls.append((_filename(source), longest_side, quality))
        return self.THUMBNAIL

    def square_jpeg(self, source: IO[bytes], side: int, quality: int) -> bytes:
        self._fail_if_asked(source)
        self.square_calls.append((_filename(source), side, quality))
        return self.COVER

    def capture_date(self, source: IO[bytes]) -> date | None:
        return self.taken_on

    def _fail_if_asked(self, source: IO[bytes]) -> None:
        if _filename(source) in self.failing_names:
            raise ImageProcessingError(_filename(source))


class FakeGalleryFileStorage:
    """In-memory storage with predictable names (``gallery/{album}/{n}.{ext}``)."""

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.deleted: list[str] = []
        self._sequence = count(1)

    def save_original(self, album_id: int, extension: str, stream: IO[bytes]) -> str:
        stream.seek(0)
        return self._store(f"gallery/{album_id}", extension, stream.read())

    def save_thumbnail(self, album_id: int, content: bytes) -> str:
        return self._store(f"gallery/thumbs/{album_id}", "jpg", content)

    def save_cover(self, album_id: int, content: bytes) -> str:
        return self._store(f"gallery/covers/{album_id}", "jpg", content)

    def open(self, name: str) -> IO[bytes]:
        if name not in self.files:
            raise FileNotFoundError(name)
        stream = io.BytesIO(self.files[name])
        stream.name = name
        return stream

    def delete(self, name: str) -> None:
        self.deleted.append(name)
        self.files.pop(name, None)

    def url(self, name: str) -> str:
        return f"/ipbcb/media/{name}"

    def _store(self, folder: str, extension: str, content: bytes) -> str:
        name = f"{folder}/{next(self._sequence)}.{extension}"
        self.files[name] = content
        return name


class FakeClock:
    """A settable clock for repeatable time (``core.time.clock.Clock``)."""

    START = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)

    def __init__(self, now: datetime = START) -> None:
        self.current = now

    def now(self) -> datetime:
        return self.current

    def advance(self, delta: timedelta) -> None:
        self.current += delta


class FakeAlbumRepository:
    """Live albums in ``records``; trashed ones move to ``trashed`` (``FakeTrashRepository``).
    Enforces sibling-unique names among live albums like the database constraints do, and sets
    ``updated_at`` from its clock on every write."""

    def __init__(self, clock: FakeClock | None = None) -> None:
        self.clock = clock or FakeClock()
        self.records: dict[int, AlbumRecord] = {}
        self.trashed: dict[int, AlbumRecord] = {}
        self.albums_with_photos: set[int] = set()
        self.locked_parent_map = False
        self.touched: list[int] = []
        self.photo_repository: "FakeGalleryRepository | None" = None
        self._ids = count(1)

    def add(self, name: str, parent_id: int | None = None, cover_name: str = "") -> int:
        """Test helper: insert an album last among its siblings, bypassing every check."""
        album_id = next(self._ids)
        self.records[album_id] = AlbumRecord(
            id=album_id,
            name=name,
            parent_id=parent_id,
            description="",
            event_date=None,
            position=self.next_position(parent_id),
            cover_name=cover_name,
            updated_at=self.clock.now(),
        )
        return album_id

    def exists(self, album_id: int) -> bool:
        return album_id in self.records

    def get_record(self, album_id: int) -> AlbumRecord | None:
        return self.records.get(album_id)

    def list_records(self) -> list[AlbumRecord]:
        return list(self.records.values())

    def sibling_name_taken(self, name: str, parent_id: int | None, exclude_id: int | None) -> bool:
        return any(
            r.name == name and r.parent_id == parent_id and r.id != exclude_id
            for r in self.records.values()
        )

    def live_sibling_named(self, name: str, parent_id: int | None) -> int | None:
        return next(
            (r.id for r in self.records.values() if r.name == name and r.parent_id == parent_id),
            None,
        )

    def parent_map(self, lock: bool) -> dict[int, int | None]:
        self.locked_parent_map = self.locked_parent_map or lock
        return {album_id: r.parent_id for album_id, r in self.records.items()}

    def next_position(self, parent_id: int | None) -> int:
        if parent_id is not None and parent_id in self.trashed:
            raise AlbumNotFoundError(parent_id)
        positions = [r.position for r in self.records.values() if r.parent_id == parent_id]
        return max(positions) + 1 if positions else 0

    def create(self, album: AlbumCreate, position: int) -> int:
        if self.sibling_name_taken(album.name, album.parent_id, None):
            raise DuplicateAlbumNameError(album.name, album.parent_id)
        album_id = next(self._ids)
        self.records[album_id] = AlbumRecord(
            id=album_id,
            position=position,
            cover_name="",
            updated_at=self.clock.now(),
            **album.model_dump(),
        )
        return album_id

    def update(self, album_id: int, fields: Mapping[str, object]) -> None:
        changes = {**fields, "updated_at": self.clock.now()}
        self.records[album_id] = self.records[album_id].model_copy(update=changes)

    def child_ids(self, parent_id: int | None) -> list[int]:
        children = [r for r in self.records.values() if r.parent_id == parent_id]
        return [r.id for r in sorted(children, key=lambda r: (r.position, r.id))]

    def apply_order(self, ids: Sequence[int]) -> None:
        for index, album_id in enumerate(ids):
            if self.records[album_id].position != index:
                self.update(album_id, {"position": index})

    def has_photos(self, album_id: int) -> bool:
        return album_id in self.albums_with_photos

    def set_cover_name(self, album_id: int, name: str | None) -> None:
        self.update(album_id, {"cover_name": name or ""})

    def set_cover_name_if_absent(self, album_id: int, name: str) -> bool:
        if self.records[album_id].cover_name:
            return False
        self.set_cover_name(album_id, name)
        return True

    def touch(self, ids: Sequence[int]) -> None:
        for album_id in ids:
            if album_id in self.records:
                self.touched.append(album_id)
                self.update(album_id, {})

    def touch_photos_of(self, album_id: int) -> None:
        if self.photo_repository is not None:
            self.photo_repository.touch_album(album_id)


class FakeGalleryRepository:
    """Live photos in ``photos``; trashed ones move to ``trashed``. Shares album names and "has
    photos" with a ``FakeAlbumRepository`` and uses its clock.

    ``fail_on_create`` makes ``create_photo`` raise, as a database failure would.
    """

    UPLOADED_AT = datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc)

    def __init__(self, albums: FakeAlbumRepository) -> None:
        self.albums = albums
        albums.photo_repository = self
        self.photos: dict[int, PhotoView] = {}
        self.trashed: dict[int, PhotoView] = {}
        self.positions: dict[int, int] = {}
        self.thumbnails: dict[int, str] = {}
        self.images: dict[int, str] = {}
        self.created: list[NewPhoto] = []
        self.fail_on_create = False
        self._ids = count(1)

    def add(self, album_id: int, name: str = "photo.jpg", thumbnail: str = "") -> int:
        """Test helper: a stored photo, bypassing the upload."""
        photo = NewPhoto(
            album_id=album_id,
            image_name=f"gallery/{album_id}/{name}",
            thumbnail_name=thumbnail,
            name=name,
            date_taken=None,
            uploader_id=None,
        )
        return self._insert(photo)

    def list_all_photos(self) -> list[PhotoView]:
        return [self.photos[i] for i in sorted(self.photos, key=self._sort_key)]

    def list_photos_by_album(self, album_id: int) -> list[PhotoView]:
        return [p for p in self.list_all_photos() if p.album_id == album_id]

    def list_photos_changed_since(self, since: datetime) -> list[PhotoView]:
        return [p for p in self.list_all_photos() if p.updated_at > since]

    def get_photo(self, photo_id: int) -> PhotoView | None:
        return self.photos.get(photo_id)

    def create_photo(self, photo: NewPhoto) -> PhotoView:
        if self.fail_on_create:
            raise RuntimeError("database unavailable")
        if photo.album_id not in self.albums.records:
            raise AlbumNotFoundError(photo.album_id)
        self.created.append(photo)
        return self.photos[self._insert(photo)]

    def update_photo(self, photo_id: int, fields: Mapping[str, object]) -> None:
        changes = {**fields, "updated_at": self.albums.clock.now()}
        self.photos[photo_id] = self.photos[photo_id].model_copy(update=changes)

    def move_photo(self, photo_id: int, album_id: int) -> None:
        if album_id not in self.albums.records:
            raise AlbumNotFoundError(album_id)
        position = self._next_position(album_id)
        self.positions[photo_id] = position
        name = self.albums.records[album_id].name
        self.update_photo(
            photo_id, {"album_id": album_id, "album_name": name, "position": position}
        )
        self.albums.albums_with_photos.add(album_id)

    def photo_ids(self, album_id: int) -> list[int]:
        return [p.id for p in self.list_photos_by_album(album_id)]

    def apply_order(self, ids: Sequence[int]) -> None:
        for index, photo_id in enumerate(ids):
            if self.positions[photo_id] != index:
                self.positions[photo_id] = index
                self.update_photo(photo_id, {"position": index})

    def photos_without_thumbnail(self) -> Iterator[tuple[int, int, str]]:
        for photo_id in sorted(self.photos):
            if not self.thumbnails.get(photo_id):
                yield photo_id, self.photos[photo_id].album_id, self.images[photo_id]

    def set_thumbnail(self, photo_id: int, name: str) -> None:
        self.thumbnails[photo_id] = name
        self.update_photo(photo_id, {"thumbnail_path": f"/ipbcb/media/{name}"})

    def touch_album(self, album_id: int) -> None:
        """Backs ``FakeAlbumRepository.touch_photos_of``."""
        for photo in list(self.photos.values()):
            if photo.album_id == album_id:
                self.update_photo(photo.id, {})

    def _insert(self, photo: NewPhoto) -> int:
        photo_id = next(self._ids)
        position = self._next_position(photo.album_id)
        self.positions[photo_id] = position
        self.images[photo_id] = photo.image_name
        self.thumbnails[photo_id] = photo.thumbnail_name
        self.photos[photo_id] = PhotoView(
            id=photo_id,
            name=photo.name,
            description="",
            album_id=photo.album_id,
            album_name=self.albums.records[photo.album_id].name,
            image_path=f"/ipbcb/media/{photo.image_name}",
            thumbnail_path=f"/ipbcb/media/{photo.thumbnail_name}" if photo.thumbnail_name else None,
            date_taken=photo.date_taken,
            uploaded_at=self.UPLOADED_AT,
            position=position,
            updated_at=self.albums.clock.now(),
        )
        self.albums.albums_with_photos.add(photo.album_id)
        return photo_id

    def _next_position(self, album_id: int) -> int:
        positions = [self.positions[p.id] for p in self.photos.values() if p.album_id == album_id]
        return max(positions) + 1 if positions else 0

    def _sort_key(self, photo_id: int) -> tuple[int, int]:
        return (self.positions[photo_id], photo_id)
