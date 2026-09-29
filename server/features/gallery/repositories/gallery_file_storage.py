from typing import IO
from uuid import uuid4

from django.core.files import File
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

GALLERY_FOLDER = "gallery"
THUMBNAIL_FOLDER = f"{GALLERY_FOLDER}/thumbs"
COVER_FOLDER = f"{GALLERY_FOLDER}/covers"


class DefaultStorageGalleryFileStorage:
    """Gallery files on Django's default storage, under random names.

    The album id in the path only spreads files; nothing reads it back, so renaming or moving an
    album or a photo never moves a file (specs/013-gallery-write-api FR-017). Everything lives
    under ``gallery/``, readable only by members (specs/009-protected-media-access).
    """

    def save_original(self, album_id: int, extension: str, stream: IO[bytes]) -> str:
        """Stream an original to ``gallery/{album_id}/{uuid}.{extension}``.

        >>> storage.save_original(7, "jpg", open("photo.jpg", "rb"))
        'gallery/7/9b1e....jpg'
        """
        stream.seek(0)
        return default_storage.save(
            _random_name(f"{GALLERY_FOLDER}/{album_id}", extension), File(stream)
        )

    def save_thumbnail(self, album_id: int, content: bytes) -> str:
        """>>> storage.save_thumbnail(7, jpeg_bytes)
        'gallery/thumbs/7/c4d0....jpg'
        """
        return default_storage.save(
            _random_name(f"{THUMBNAIL_FOLDER}/{album_id}", "jpg"), ContentFile(content)
        )

    def save_cover(self, album_id: int, content: bytes) -> str:
        """>>> storage.save_cover(7, jpeg_bytes)
        'gallery/covers/7/3f2a....jpg'
        """
        return default_storage.save(
            _random_name(f"{COVER_FOLDER}/{album_id}", "jpg"), ContentFile(content)
        )

    def open(self, name: str) -> IO[bytes]:
        """Open a stored file for reading; ``FileNotFoundError`` when it is gone.

        >>> storage.open("gallery/7/9b1e....jpg").read(2)
        b'\\xff\\xd8'
        """
        stored: IO[bytes] = default_storage.open(name, "rb")
        return stored

    def delete(self, name: str) -> None:
        """Remove ``name``; a file already gone is not an error.

        >>> storage.delete("gallery/covers/7/3f2a....jpg")
        """
        default_storage.delete(name)

    def url(self, name: str) -> str:
        """URL path of a stored file, e.g. ``/ipbcb/media/gallery/7/9b1e....jpg``."""
        return str(default_storage.url(name))


def _random_name(folder: str, extension: str) -> str:
    return f"{folder}/{uuid4().hex}.{extension}"
