import logging
from functools import partial
from typing import IO

from django.db import transaction

from core.domain.exceptions import AlbumNotFoundError, ValidationError
from core.files.image_validation import detect_image_extension
from features.gallery.domain.image_limits import DERIVATIVE_JPEG_QUALITY, ensure_within_pixel_limit
from features.gallery.imaging.interfaces import ImageProcessor
from features.gallery.repositories.interfaces import AlbumRepository, GalleryFileStorage

logger = logging.getLogger("features.gallery")

# One constant so the cover size can change later (specs/013-gallery-write-api).
COVER_SIDE_PX = 1000


class AlbumCoverService:
    """An album's own cover: a server-made square JPEG, independent of any photo.

    Storage cannot join a transaction, so a new file is written first, the row is switched in a
    transaction, and the replaced file is removed only after commit (as MemberPhotoService does).
    """

    def __init__(
        self,
        album_repository: AlbumRepository,
        file_storage: GalleryFileStorage,
        image_processor: ImageProcessor,
    ) -> None:
        self._albums = album_repository
        self._storage = file_storage
        self._images = image_processor

    def replace_cover(self, album_id: int, upload: IO[bytes]) -> None:
        """Validate ``upload`` like a photo, crop it to the square and make it the own cover.

        On any validation failure the previous cover stays.

        >>> service.replace_cover(7, open("capa.png", "rb"))
        """
        self._require_album(album_id)
        detect_image_extension(upload)
        new_name = self._storage.save_cover(album_id, self._square(upload))
        try:
            self._switch_cover(album_id, new_name)
        except Exception:
            self._storage.delete(new_name)
            raise

    def remove_cover(self, album_id: int) -> None:
        """Leave the album without an own cover; nothing regenerates one.

        >>> service.remove_cover(7)
        """
        self._require_album(album_id)
        self._switch_cover(album_id, None)

    def needs_first_cover(self, album_id: int) -> bool:
        """True when the album has neither photos nor an own cover — the moment an upload
        gives it its automatic cover.

        >>> service.needs_first_cover(7)
        True
        """
        record = self._albums.get_record(album_id)
        return (
            record is not None and not record.cover_name and not self._albums.has_photos(album_id)
        )

    def cover_from_photo(self, album_id: int, source: IO[bytes]) -> None:
        """Automatic cover from an accepted photo. A failure is logged, never raised: the photo
        itself was accepted and stays (spec Edge Cases).

        >>> service.cover_from_photo(7, open("IMG_0042.jpg", "rb"))
        """
        try:
            new_name = self._storage.save_cover(album_id, self._square(source))
        except (ValidationError, OSError) as exc:
            logger.warning(
                "gallery_auto_cover_failed",
                extra={"album_id": album_id, "error": type(exc).__name__},
            )
            return
        if not self._albums.set_cover_name_if_absent(album_id, new_name):
            self._storage.delete(new_name)

    def _square(self, source: IO[bytes]) -> bytes:
        ensure_within_pixel_limit(*self._images.dimensions(source))
        return self._images.square_jpeg(source, COVER_SIDE_PX, DERIVATIVE_JPEG_QUALITY)

    def _switch_cover(self, album_id: int, new_name: str | None) -> None:
        with transaction.atomic():
            old = self._albums.get_record(album_id)
            self._albums.set_cover_name(album_id, new_name)
            if old is not None and old.cover_name:
                transaction.on_commit(partial(self._storage.delete, old.cover_name), robust=True)

    def _require_album(self, album_id: int) -> None:
        if not self._albums.exists(album_id):
            raise AlbumNotFoundError(album_id)
