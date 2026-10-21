"""What an event image must be (specs/020-church-events, Definitions → Image).

The app crops to 16:9 before uploading; the server re-checks with a small tolerance and stores a
JPEG fitted within 1920 x 1080. Each limit is one constant so it can change later.
"""

from typing import Final

from core.domain.exceptions import EventImageInvalidError

MAX_EVENT_IMAGE_BYTES: Final = 10 * 1024 * 1024
# GIF is accepted by core validation for the gallery, not here: a poster is never animated.
EVENT_IMAGE_EXTENSIONS: Final = frozenset({"jpg", "png", "webp"})
MIN_WIDTH: Final = 640
MIN_HEIGHT: Final = 360
TARGET_RATIO: Final = 16 / 9
RATIO_TOLERANCE: Final = 0.02
MAX_WIDTH: Final = 1920
MAX_HEIGHT: Final = 1080
# A 10 MB file can still decode to hundreds of MB of pixels; phone cameras (12-48 MP) pass.
MAX_PIXELS: Final = 50_000_000
JPEG_QUALITY: Final = 85


def ensure_event_image_extension(extension: str) -> None:
    """Refuse a decoded format events do not take.

    >>> ensure_event_image_extension("gif")
    Traceback (most recent call last):
    EventImageInvalidError: Formato de imagem não suportado para eventos: GIF. ...
    """
    if extension not in EVENT_IMAGE_EXTENSIONS:
        raise EventImageInvalidError(
            f"Formato de imagem não suportado para eventos: {extension.upper()}. "
            "Use JPEG, PNG ou WEBP."
        )


def ensure_event_image_shape(width: int, height: int) -> None:
    """Refuse an image too large to decode, too small, or not 16:9 within the tolerance.
    ``width`` and ``height`` are as displayed (EXIF orientation applied).

    >>> ensure_event_image_shape(1920, 1080)
    """
    _ensure_pixel_count(width, height)
    _ensure_minimum_size(width, height)
    _ensure_ratio(width, height)


def _ensure_pixel_count(width: int, height: int) -> None:
    if width * height > MAX_PIXELS:
        raise EventImageInvalidError(
            f"Imagem grande demais: {width}x{height} pixels. "
            f"O máximo é {MAX_PIXELS // 1_000_000} megapixels."
        )


def _ensure_minimum_size(width: int, height: int) -> None:
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        raise EventImageInvalidError(
            f"Imagem pequena demais: {width}x{height} pixels. O mínimo é {MIN_WIDTH}x{MIN_HEIGHT}."
        )


def _ensure_ratio(width: int, height: int) -> None:
    ratio = width / height
    if abs(ratio - TARGET_RATIO) <= TARGET_RATIO * RATIO_TOLERANCE:
        return
    raise EventImageInvalidError(
        f"Proporção da imagem {width}x{height} é {ratio:.2f}; esperado 16:9 "
        f"({TARGET_RATIO:.2f}) com tolerância de {RATIO_TOLERANCE:.0%}."
    )
