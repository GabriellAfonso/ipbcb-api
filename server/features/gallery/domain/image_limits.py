"""Limits shared by every gallery image derivative (specs/013-gallery-write-api)."""

from core.domain.exceptions import ImageTooLargeError

# A 10 MB file can still decode to hundreds of MB of pixels; phone cameras (12-48 MP) pass.
MAX_UPLOAD_PIXELS = 50_000_000
DERIVATIVE_JPEG_QUALITY = 85


def ensure_within_pixel_limit(width: int, height: int, max_pixels: int = MAX_UPLOAD_PIXELS) -> None:
    """Refuse an image whose pixel count exceeds ``max_pixels``.

    >>> ensure_within_pixel_limit(8000, 6000)
    Traceback (most recent call last):
    ImageTooLargeError: Imagem grande demais: 8000x6000 pixels. O máximo é 50 megapixels.
    """
    if width * height > max_pixels:
        raise ImageTooLargeError(width, height, max_pixels)
