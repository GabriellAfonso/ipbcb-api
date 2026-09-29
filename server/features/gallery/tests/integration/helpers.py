"""Shared builders for the gallery API tests: real image bytes and a gallery manager client."""

import io

from PIL import Image
from rest_framework.test import APIClient

from conftest import make_role_client
from core.domain.access import Role

_EXIF_IFD = 0x8769
_DATE_TIME_ORIGINAL = 0x9003


def image_file(
    name: str = "IMG_0042.jpg",
    size: tuple[int, int] = (1600, 1200),
    fmt: str = "JPEG",
    taken: str | None = None,
) -> io.BytesIO:
    """An encoded image as a named upload; ``taken`` sets EXIF ``DateTimeOriginal``."""
    buffer = io.BytesIO()
    extra: dict[str, object] = {}
    if taken is not None:
        exif = Image.Exif()
        exif.get_ifd(_EXIF_IFD)[_DATE_TIME_ORIGINAL] = taken
        extra["exif"] = exif
    Image.new("RGB", size, "teal").save(buffer, format=fmt, **extra)
    buffer.seek(0)
    buffer.name = name
    return buffer


def text_file(name: str = "notes.jpg") -> io.BytesIO:
    buffer = io.BytesIO(b"this is not an image")
    buffer.name = name
    return buffer


def gallery_manager(role: Role = Role.MEDIA, username: str = "media_manager") -> APIClient:
    """A role holder who is also a member, so the same client can write and read back."""
    client, user = make_role_client(role, username=username)
    user.profile.is_member = True
    user.profile.save()
    return client


def decoded_size(content: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(content)) as image:
        return image.size
