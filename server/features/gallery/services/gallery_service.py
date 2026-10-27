import logging
from collections.abc import Callable, Sequence
from functools import partial
from typing import IO
from uuid import UUID

from django.db import transaction

from core.domain.exceptions import (
    AlbumNotFoundError,
    ClientUploadIdTakenError,
    ImageProcessingError,
    NoPhotoAcceptedError,
    NoVideoAcceptedError,
    PhotoNotFoundError,
    UploadedPhotoTrashedError,
    ValidationError,
)
from core.files.image_validation import detect_image_extension
from core.files.upload_size import upload_size
from core.files.video_validation import detect_video_extension
from features.gallery.domain.gallery_rules import fit_photo_name
from features.gallery.domain.image_limits import DERIVATIVE_JPEG_QUALITY, ensure_within_pixel_limit
from features.gallery.domain.media_types import VIDEO
from features.gallery.domain.upload_rules import ensure_valid_client_upload
from features.gallery.dtos.gallery_dtos import (
    ClientUploadMatch,
    FileSizeBackfillReport,
    NewPhoto,
    PhotoChanges,
    PhotoView,
    RejectedFile,
    ThumbnailBackfillReport,
    UploadResult,
    VideoUploadMeta,
)
from core.files.imaging.interfaces import ImageProcessor
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
    """Gallery items (photos and videos): reads, upload, metadata, order and the backfills.

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
        store = partial(self._upload_batch, album_id, [files[0]], uploader_id, client_upload_id)
        return self._answer_race(client_upload_id, uploader_id, store)

    def upload_video(
        self,
        album_id: int,
        video: IO[bytes],
        poster: IO[bytes],
        upload: VideoUploadMeta,
        uploader_id: UUID | None = None,
    ) -> UploadResult:
        """Store one video as sent, with the poster as its thumbnail (specs/023-gallery-videos).

        The client upload id is required and answered as for a photo: a retry of a stored video
        returns it, or raises ``UploadedPhotoTrashedError`` when it is in the trash. A refused
        video or poster raises ``NoVideoAcceptedError``; nothing is stored then.

        >>> meta = VideoUploadMeta(duration_ms=45000, client_upload_id=upload_id)
        >>> service.upload_video(7, open("culto.mp4", "rb"), open("capa.jpg", "rb"), meta)
        UploadResult(accepted=[PhotoView(id=52, ..., media_type='video', ...)], rejected=[])
        """
        ensure_valid_client_upload(upload.client_upload_id, 1)
        existing = self._existing_upload(upload.client_upload_id, uploader_id)
        if existing is not None:
            return existing
        store = partial(self._store_video, album_id, video, poster, upload, uploader_id)
        return self._answer_race(upload.client_upload_id, uploader_id, store)

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

    def fill_missing_file_sizes(self) -> FileSizeBackfillReport:
        """Record the size of every item stored without one (before feature 023); a missing
        file is skipped and reported. Idempotent: only items without a size are read.

        >>> service.fill_missing_file_sizes()
        FileSizeBackfillReport(filled=412, skipped_ids=[7])
        """
        filled, skipped = 0, []
        for photo_id, image_name in self._repository.items_without_file_size():
            size = self._stored_size(image_name)
            if size is None:
                skipped.append(photo_id)
                continue
            self._repository.set_file_size(photo_id, size)
            filled += 1
        return FileSizeBackfillReport(filled=filled, skipped_ids=skipped)

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
                new_photo = self._new_photo(album_id, f, uploader_id, client_upload_id)
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

    def _answer_race(
        self, client_upload_id: str, uploader_id: UUID | None, store: Callable[[], UploadResult]
    ) -> UploadResult:
        """First upload of an id, photo or video. A concurrent request with the same id may store
        its item between our lookup and our insert; the unique constraint then refuses ours,
        ``_persist`` has already removed our files, and we answer as a retry (spec 016 R-04)."""
        try:
            return store()
        except ClientUploadIdTakenError:
            existing = self._existing_upload(client_upload_id, uploader_id)
            if existing is None:
                raise
            return existing

    @staticmethod
    def _new_photo(
        album_id: int, original: IO[bytes], uploader_id: UUID | None, client_upload_id: str | None
    ) -> NewPhoto:
        """The row to write, before its files exist: ``_persist`` fills in their names."""
        return NewPhoto(
            album_id=album_id,
            image_name="",
            thumbnail_name="",
            name=fit_photo_name(getattr(original, "name", "") or ""),
            date_taken=None,
            uploader_id=uploader_id,
            client_upload_id=client_upload_id,
            file_size=upload_size(original),
        )

    def _store_one(self, upload: IO[bytes], extension: str, new_photo: NewPhoto) -> PhotoView:
        """Derive, store and record one validated photo."""
        thumbnail = self._thumbnail(upload)
        dated = new_photo.model_copy(update={"date_taken": self._images.capture_date(upload)})
        return self._write_item(upload, extension, thumbnail, dated, cover_source=upload)

    def _store_video(
        self,
        album_id: int,
        video: IO[bytes],
        poster: IO[bytes],
        upload: VideoUploadMeta,
        uploader_id: UUID | None,
    ) -> UploadResult:
        """Check, store and record one video; its poster is the thumbnail and the first cover."""
        self._require_album(album_id)
        extension, thumbnail = self._checked_video(video, poster)
        fields = {
            "media_type": VIDEO,
            "duration_ms": upload.duration_ms,
            "date_taken": upload.date_taken,
        }
        new_video = self._new_photo(album_id, video, uploader_id, upload.client_upload_id)
        stored = self._write_item(
            video, extension, thumbnail, new_video.model_copy(update=fields), cover_source=poster
        )
        return UploadResult(accepted=[stored])

    def _checked_video(self, video: IO[bytes], poster: IO[bytes]) -> tuple[str, bytes]:
        """The video's extension and the poster's thumbnail, or ``NoVideoAcceptedError`` with
        the reason under the video's filename: a bad poster refuses the whole upload."""
        try:
            extension = detect_video_extension(video)
        except ValidationError as exc:
            raise _video_refused(video, str(exc)) from None
        try:
            detect_image_extension(poster)
            thumbnail = self._thumbnail(poster)
        except ValidationError as exc:
            raise _video_refused(video, f"Imagem de capa: {exc}") from None
        return extension, thumbnail

    def _write_item(
        self,
        original: IO[bytes],
        extension: str,
        thumbnail: bytes,
        new_photo: NewPhoto,
        cover_source: IO[bytes],
    ) -> PhotoView:
        """Store and record one checked item; give the album its first cover from
        ``cover_source`` (the photo itself, or a video's poster)."""
        album_id = new_photo.album_id
        first_in_album = self._covers.needs_first_cover(album_id)
        stored = self._persist(original, extension, thumbnail, new_photo)
        if first_in_album:
            self._covers.cover_from_photo(album_id, cover_source)
        return stored

    def _thumbnail(self, image: IO[bytes]) -> bytes:
        """Pixel limit, then the thumbnail: both before anything is written."""
        ensure_within_pixel_limit(*self._images.dimensions(image))
        return self._images.bounded_jpeg(image, THUMBNAIL_LONGEST_SIDE_PX, DERIVATIVE_JPEG_QUALITY)

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

    def _stored_size(self, name: str) -> int | None:
        try:
            return self._storage.size(name)
        except OSError:  # FileNotFoundError included
            return None

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


def _video_refused(video: IO[bytes], reason: str) -> NoVideoAcceptedError:
    filename = getattr(video, "name", "") or ""
    return NoVideoAcceptedError([RejectedFile(filename=filename, reason=reason).model_dump()])


def _log_existing_upload(match: ClientUploadMatch, uploader_id: UUID | None) -> None:
    """One line per retry answered from an existing photo, ids only (spec 016 FR-019)."""
    event = "gallery_upload_original_trashed" if match.trashed else "gallery_upload_deduplicated"
    actor_id = str(uploader_id) if uploader_id is not None else None
    logger.info(event, extra={"photo_id": match.photo_id, "actor_id": actor_id})
