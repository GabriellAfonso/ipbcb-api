from collections.abc import Sequence
from datetime import date
from typing import IO
from uuid import UUID

from django.db import transaction

from core.domain.exceptions import (
    AlbumNotFoundError,
    ImageProcessingError,
    NoPhotoAcceptedError,
    PhotoNotFoundError,
    ValidationError,
)
from core.files.image_validation import detect_image_extension
from features.gallery.domain.gallery_rules import fit_photo_name
from features.gallery.domain.image_limits import DERIVATIVE_JPEG_QUALITY, ensure_within_pixel_limit
from features.gallery.dtos.gallery_dtos import (
    NewPhoto,
    PhotoChanges,
    PhotoView,
    RejectedFile,
    ThumbnailBackfillReport,
    UploadResult,
)
from features.gallery.imaging.interfaces import ImageProcessor
from features.gallery.repositories.interfaces import (
    AlbumRepository,
    GalleryFileStorage,
    GalleryRepository,
)
from features.gallery.services.album_cover_service import AlbumCoverService
from features.gallery.services.ordering import ensure_exact_order
from features.gallery.services.photo_ordering import order_photos_by_tree

# One constant so the thumbnail size can change later (specs/013-gallery-write-api).
THUMBNAIL_LONGEST_SIDE_PX = 1000


class GalleryService:
    """Photos: reads, upload, metadata, order and the thumbnail backfill.

    Files are written before the row and deleted if the row cannot be written, so no photo is
    ever committed without both its original and its thumbnail (research R-05).
    """

    def __init__(
        self,
        repository: GalleryRepository,
        album_repository: AlbumRepository,
        file_storage: GalleryFileStorage,
        image_processor: ImageProcessor,
        cover_service: AlbumCoverService,
    ) -> None:
        self._repository = repository
        self._albums = album_repository
        self._storage = file_storage
        self._images = image_processor
        self._covers = cover_service

    def list_all_photos(self) -> list[PhotoView]:
        """Every photo, by the tree order of its album, then position.

        >>> [photo.album_name for photo in service.list_all_photos()]
        ['Retiros', 'Retiros', '2026']
        """
        return order_photos_by_tree(self._repository.list_all_photos(), self._albums.list_records())

    def list_photos_by_album(self, album_id: int) -> list[PhotoView]:
        """Photos directly in the album, never those of its sub-albums.

        >>> service.list_photos_by_album(7)[0].album_id
        7
        """
        self._require_album(album_id)
        return self._repository.list_photos_by_album(album_id)

    def upload_photos(
        self, album_id: int, files: Sequence[IO[bytes]], uploader_id: UUID | None = None
    ) -> UploadResult:
        """Validate and store photos in an album, each file on its own.

        Raises ``NoPhotoAcceptedError`` (with every reason) when no file was accepted.

        >>> service.upload_photos(1, [open("photo.jpg", "rb")], user_id).accepted[0].name
        'photo.jpg'
        """
        self._require_album(album_id)
        result = UploadResult()

        for f in files:
            name = getattr(f, "name", "") or ""

            # One bad file must not fail the batch, so the shared validator is caught
            # per file instead of bubbling up.
            try:
                extension = detect_image_extension(f)
                result.accepted.append(self._store_one(album_id, f, name, extension, uploader_id))
            except ValidationError as exc:
                result.rejected.append(RejectedFile(filename=name, reason=str(exc)))

        if not result.accepted:
            raise NoPhotoAcceptedError([rejected.model_dump() for rejected in result.rejected])
        return result

    def update_photo(self, photo_id: int, changes: PhotoChanges) -> PhotoView:
        """Edit ``name``, ``description``, ``date_taken``; ``album_id`` moves it to the end of
        another album. Files never move.

        >>> service.update_photo(12, PhotoChanges(description="Culto de Páscoa")).description
        'Culto de Páscoa'
        """
        current = self._require_photo(photo_id)
        sent = changes.model_fields_set
        with transaction.atomic():
            if "album_id" in sent and changes.album_id != current.album_id:
                self._move(photo_id, changes.album_id)
            fields = {
                key: getattr(changes, key)
                for key in ("name", "description", "date_taken")
                if key in sent
            }
            if fields:
                self._repository.update_photo(photo_id, fields)
        return self._require_photo(photo_id)

    def reorder_photos(self, album_id: int, ids: Sequence[int]) -> None:
        """Replace the order of the album's photos with ``ids``.

        >>> service.reorder_photos(7, [12, 10, 11])
        """
        self._require_album(album_id)
        with transaction.atomic():
            ensure_exact_order(ids, self._repository.photo_ids(album_id))
            self._repository.apply_order(ids)

    def fill_missing_thumbnails(self) -> ThumbnailBackfillReport:
        """Thumbnail every photo that has none; unreadable originals are skipped and reported.
        Idempotent: only photos without a thumbnail are read.

        >>> service.fill_missing_thumbnails()
        ThumbnailBackfillReport(filled=41, skipped_ids=[7])
        """
        filled, skipped = 0, []
        for photo_id, album_id, image_name in self._repository.photos_without_thumbnail():
            if self._backfill_one(photo_id, album_id, image_name):
                filled += 1
            else:
                skipped.append(photo_id)
        return ThumbnailBackfillReport(filled=filled, skipped_ids=skipped)

    def _store_one(
        self, album_id: int, upload: IO[bytes], name: str, extension: str, uploader_id: UUID | None
    ) -> PhotoView:
        """Derive, store and record one validated file; give the album its first cover."""
        thumbnail, taken_on = self._derive(upload)
        first_in_album = self._covers.needs_first_cover(album_id)
        photo = self._persist(
            album_id, upload, extension, thumbnail, fit_photo_name(name), taken_on, uploader_id
        )
        if first_in_album:
            self._covers.cover_from_photo(album_id, upload)
        return photo

    def _derive(self, upload: IO[bytes]) -> tuple[bytes, date | None]:
        """Pixel limit, thumbnail and EXIF date — all before anything is written."""
        ensure_within_pixel_limit(*self._images.dimensions(upload))
        thumbnail = self._images.bounded_jpeg(
            upload, THUMBNAIL_LONGEST_SIDE_PX, DERIVATIVE_JPEG_QUALITY
        )
        return thumbnail, self._images.capture_date(upload)

    def _persist(
        self,
        album_id: int,
        upload: IO[bytes],
        extension: str,
        thumbnail: bytes,
        name: str,
        taken_on: date | None,
        uploader_id: UUID | None,
    ) -> PhotoView:
        written: list[str] = []
        try:
            written.append(self._storage.save_original(album_id, extension, upload))
            written.append(self._storage.save_thumbnail(album_id, thumbnail))
            return self._repository.create_photo(
                NewPhoto(
                    album_id=album_id,
                    image_name=written[0],
                    thumbnail_name=written[1],
                    name=name,
                    date_taken=taken_on,
                    uploader_id=uploader_id,
                )
            )
        except Exception:
            for stored in written:
                self._storage.delete(stored)
            raise

    def _backfill_one(self, photo_id: int, album_id: int, image_name: str) -> bool:
        try:
            with self._storage.open(image_name) as original:
                thumbnail = self._images.bounded_jpeg(
                    original, THUMBNAIL_LONGEST_SIDE_PX, DERIVATIVE_JPEG_QUALITY
                )
        except (FileNotFoundError, OSError, ImageProcessingError):
            return False
        self._repository.set_thumbnail(photo_id, self._storage.save_thumbnail(album_id, thumbnail))
        return True

    def _move(self, photo_id: int, album_id: int | None) -> None:
        if album_id is None:
            raise ValidationError(f"Field 'album_id' must be an album id, got {album_id!r}.")
        self._require_album(album_id)
        self._repository.move_photo(photo_id, album_id)

    def _require_album(self, album_id: int) -> None:
        if not self._albums.exists(album_id):
            raise AlbumNotFoundError(album_id)

    def _require_photo(self, photo_id: int) -> PhotoView:
        photo = self._repository.get_photo(photo_id)
        if photo is None:
            raise PhotoNotFoundError(photo_id)
        return photo
