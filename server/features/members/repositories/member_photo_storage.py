from typing import IO
from uuid import uuid4

from django.core.files import File
from django.core.files.storage import default_storage

MEMBER_PHOTO_FOLDER = "members"


class DefaultStorageMemberPhotoStorage:
    """Member photos on Django's default storage, under ``members/<uuid4 hex>.<ext>``.

    No member name or id in the path. Reading is gated by the leader-only media rule for
    ``members/`` (specs/009-protected-media-access); the random name is defence in depth if
    the media directory were ever re-published.
    """

    def save(self, extension: str, upload: IO[bytes]) -> str:
        """Stream ``upload`` to storage and return the stored name.

        >>> storage.save("png", open("photo.png", "rb"))
        'members/6f1c2d0e....png'
        """
        return default_storage.save(
            f"{MEMBER_PHOTO_FOLDER}/{uuid4().hex}.{extension}", File(upload)
        )

    def delete(self, name: str) -> None:
        """Remove ``name``; a file already gone is not an error.

        >>> storage.delete("members/6f1c2d0e....png")
        """
        default_storage.delete(name)
