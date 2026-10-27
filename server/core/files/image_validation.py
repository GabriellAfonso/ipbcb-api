"""Content-based validation for uploaded images.

The filename and the Content-Type header are supplied by the client; the format Pillow
can actually decode is not. Every stored extension is derived from the decoded format,
so a PNG named ``evil.html`` is stored as ``.png``.

Messages are in Portuguese on purpose: they reach the app user through the canonical
error body built by ``core.http.exceptions``.
"""

from typing import IO, Final

from PIL import Image, UnidentifiedImageError

from core.domain.exceptions import ValidationError
from core.files.upload_size import upload_size

MAX_IMAGE_BYTES: Final = 10 * 1024 * 1024

# Pillow format name -> extension used on disk. SVG is absent on purpose: it is a
# scriptable document, and Pillow does not decode it anyway.
ALLOWED_IMAGE_FORMATS: Final[dict[str, str]] = {
    "JPEG": "jpg",
    "PNG": "png",
    "WEBP": "webp",
    "GIF": "gif",
}

_ACCEPTED_LABEL: Final = "Use JPEG, PNG, WEBP ou GIF."


def detect_image_extension(upload: IO[bytes], max_bytes: int = MAX_IMAGE_BYTES) -> str:
    """Return the extension to store ``upload`` under, or raise ``ValidationError``.

    Size is checked before the bytes are decoded, so an oversized upload is refused
    without being loaded.

    >>> detect_image_extension(open("avatar.jpg", "rb"))
    'jpg'
    """
    _reject_oversized(upload, max_bytes)
    image_format = _decode_format(upload)

    extension = ALLOWED_IMAGE_FORMATS.get(image_format)
    if extension is None:
        raise ValidationError(f"Formato de imagem não suportado: {image_format}. {_ACCEPTED_LABEL}")
    return extension


def _reject_oversized(upload: IO[bytes], max_bytes: int) -> None:
    """Refuse before the decode that follows, so large uploads never reach Pillow."""
    size = upload_size(upload)
    if size is None or size <= max_bytes:
        return
    raise ValidationError(
        f"Arquivo muito grande: {size} bytes. O máximo é {max_bytes} bytes "
        f"({max_bytes // (1024 * 1024)} MB)."
    )


def _decode_format(upload: IO[bytes]) -> str:
    """Return Pillow's format name, leaving the stream rewound for the caller.

    ``verify()`` consumes the image object, so ``format`` is read before it runs.
    """
    try:
        upload.seek(0)
        with Image.open(upload) as image:
            image_format = image.format or ""
            image.verify()
        return image_format
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        raise ValidationError(
            f"Formato inválido: o arquivo enviado não é uma imagem legível. {_ACCEPTED_LABEL}"
        ) from None
    finally:
        upload.seek(0)
