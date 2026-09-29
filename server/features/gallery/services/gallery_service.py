import logging
from collections.abc import Sequence
from datetime import date
from typing import IO
from uuid import UUID

from django.db import transaction

from core.domain.exceptions import (
    AlbumNotFoundError,
    ClientUploadIdTakenError,
    ImageProcessingError,
    NoPhotoAcceptedError,
    PhotoNotFoundError,
    UploadedPhotoTrashedError,
    ValidationError,
)
from core.files.image_validation import detect_image_extension
from features.gallery.domain.gallery_rules import fit_photo_name
from features.gallery.domain.image_limits import DERIVATIVE_JPEG_QUALITY, ensure_within_pixel_limit
from features.gallery.domain.upload_rules import ensure_valid_client_upload
from features.gallery.dtos.gallery_dtos import (
    ClientUploadMatch,
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

logger = logging.getLogger("features.gallery")

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

    def list_all_photos(self, member_ids: frozenset[int] = frozenset()) -> list[PhotoView]:
        """Every photo, by the tree order of its album, then position. With ``member_ids``,
        only photos in which every one of those members is tagged (AND).

        >>> [photo.album_name for photo in service.list_all_photos()]
        ['Retiros', 'Retiros', '2026']
        """
        photos = self._repository.list_all_photos(member_ids)
        return order_photos_by_tree(photos, self._albums.list_records())

    def list_photos_by_album(
        self, album_id: int, member_ids: frozenset[int] = frozenset()
    ) -> list[PhotoView]:
        """Photos directly in the album, never those of its sub-albums; ``member_ids`` filters
        as in ``list_all_photos``.

        >>> service.list_photos_by_album(7, frozenset({12}))[0].album_id
        7
        """
        self._require_album(album_id)
        return self._repository.list_photos_by_album(album_id, member_ids)

    def upload_photos(
        self,
        album_id: int,
        files: Sequence[IO[bytes]],
        uploader_id: UUID | None = None,
        client_upload_id: str | None = None,
    ) -> UploadResult:
        """Validate and store photos in an album, each file on its own.

        Raises ``NoPhotoAcceptedError`` (with every reason) when no file was accepted. With a
        ``client_upload_id`` (one file only), a retry of a photo already stored returns that
        photo and stores nothing, or raises ``UploadedPhotoTrashedError`` when it is in the
        trash; the album is then never looked up (specs/016-photo-upload-idempotency FR-009 to
        FR-012).

        >>> service.upload_photos(1, [open("photo.jpg", "rb")], user_id).accepted[0].name
        'photo.jpg'
        >>> service.upload_photos(1, [retry_file], user_id, upload_id).accepted[0].id
        41
        """
        if client_upload_id is None:
            return self._upload_batch(album_id, files, uploader_id)
        ensure_valid_client_upload(client_upload_id, len(files))
        existing = self._existing_upload(client_upload_id, uploader_id)
        if existing is not None:
            return existing
        return self._store_first(album_id, files[0], uploader_id, client_upload_id)

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

    def _upload_batch(
        self,
        album_id: int,
        files: Sequence[IO[bytes]],
        uploader_id: UUID | None,
        client_upload_id: str | None = None,
    ) -> UploadResult:
        """The feature 013 upload; ``client_upload_id`` only reaches the stored row."""
        self._require_album(album_id)
        result = UploadResult()

        for f in files:
            name = getattr(f, "name", "") or ""

            # One bad file must not fail the batch, so the shared validator is caught
            # per file instead of bubbling up.
            try:
                extension = detect_image_extension(f)
                new_photo = self._new_photo(album_id, name, uploader_id, client_upload_id)
                result.accepted.append(self._store_one(f, extension, new_photo))
            except ValidationError as exc:
                result.rejected.append(RejectedFile(filename=name, reason=str(exc)))

        if not result.accepted:
            raise NoPhotoAcceptedError([rejected.model_dump() for rejected in result.rejected])
        return result

    def _existing_upload(
        self, client_upload_id: str, uploader_id: UUID | None
    ) -> UploadResult | None:
        """The answer to a retry of a photo already stored, or ``None`` for a first upload."""
        match = self._repository.find_client_upload(client_upload_id)
        if match is None:
            return None
        _log_existing_upload(match, uploader_id)
        if match.trashed:
            raise UploadedPhotoTrashedError(client_upload_id)
        return UploadResult(accepted=[self._require_photo(match.photo_id)])

    def _store_first(
        self, album_id: int, upload: IO[bytes], uploader_id: UUID | None, client_upload_id: str
    ) -> UploadResult:
        """First upload of an id. A concurrent request with the same id may store its photo
        between our lookup and our insert; the unique constraint then refuses ours, ``_persist``
        has already removed our files, and we answer as a retry (research R-04)."""
        try:
            return self._upload_batch(album_id, [upload], uploader_id, client_upload_id)
        except ClientUploadIdTakenError:
            existing = self._existing_upload(client_upload_id, uploader_id)
            if existing is None:
                raise
            return existing

    @staticmethod
    def _new_photo(
        album_id: int, name: str, uploader_id: UUID | None, client_upload_id: str | None
    ) -> NewPhoto:
        """The row to write, before its files exist: ``_persist`` fills in their names."""
        return NewPhoto(
            album_id=album_id,
            image_name="",
            thumbnail_name="",
            name=fit_photo_name(name),
            date_taken=None,
            uploader_id=uploader_id,
            client_upload_id=client_upload_id,
        )

    def _store_one(self, upload: IO[bytes], extension: str, new_photo: NewPhoto) -> PhotoView:
        """Derive, store and record one validated file; give the album its first cover."""
        album_id = new_photo.album_id
        thumbnail, taken_on = self._derive(upload)
        first_in_album = self._covers.needs_first_cover(album_id)
        photo = self._persist(
            upload, extension, thumbnail, new_photo.model_copy(update={"date_taken": taken_on})
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
        self, upload: IO[bytes], extension: str, thumbnail: bytes, new_photo: NewPhoto
    ) -> PhotoView:
        """Write both files, then the row; on any failure delete what was written."""
        album_id = new_photo.album_id
        written: list[str] = []
        try:
            written.append(self._storage.save_original(album_id, extension, upload))
            written.append(self._storage.save_thumbnail(album_id, thumbnail))
            names = {"image_name": written[0], "thumbnail_name": written[1]}
            return self._repository.create_photo(new_photo.model_copy(update=names))
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


def _log_existing_upload(match: ClientUploadMatch, uploader_id: UUID | None) -> None:
    """One line per retry answered from an existing photo, ids only (spec 016 FR-019)."""
    event = "gallery_upload_original_trashed" if match.trashed else "gallery_upload_deduplicated"
    actor_id = str(uploader_id) if uploader_id is not None else None
    logger.info(event, extra={"photo_id": match.photo_id, "actor_id": actor_id})
