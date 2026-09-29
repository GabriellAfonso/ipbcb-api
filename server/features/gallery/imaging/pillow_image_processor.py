"""Pillow implementation of ``ImageProcessor`` — the only gallery module that imports Pillow for
derivatives (specs/013-gallery-write-api/research.md R-04). Validation of uploads stays in
``core.files.image_validation``."""

import io
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import date, datetime
from typing import IO, TypeVar

from PIL import Image, ImageOps, UnidentifiedImageError

from core.domain.exceptions import ImageProcessingError

_EXIF_IFD = 0x8769
_DATE_TIME_ORIGINAL = 0x9003
_DATE_TIME = 0x0132
_EXIF_DATE_FORMAT = "%Y:%m:%d %H:%M:%S"
_DECODE_ERRORS = (
    UnidentifiedImageError,
    OSError,
    ValueError,
    SyntaxError,
    Image.DecompressionBombError,
)

_T = TypeVar("_T")


class PillowImageProcessor:
    """``ImageProcessor`` backed by Pillow.

    >>> PillowImageProcessor().bounded_jpeg(open("photo.jpg", "rb"), 1000, 85)[:2]
    b'\\xff\\xd8'
    """

    def dimensions(self, source: IO[bytes]) -> tuple[int, int]:
        return self._with_image(source, lambda image: image.size)

    def bounded_jpeg(self, source: IO[bytes], longest_side: int, quality: int) -> bytes:
        def build(image: Image.Image) -> bytes:
            prepared = _flatten(image, longest_side)
            prepared.thumbnail((longest_side, longest_side), Image.Resampling.LANCZOS)
            return _to_jpeg(prepared, quality)

        return self._with_image(source, build)

    def square_jpeg(self, source: IO[bytes], side: int, quality: int) -> bytes:
        def build(image: Image.Image) -> bytes:
            prepared = _flatten(image, side)
            square = ImageOps.fit(
                prepared, (side, side), Image.Resampling.LANCZOS, centering=(0.5, 0.5)
            )
            return _to_jpeg(square, quality)

        return self._with_image(source, build)

    def capture_date(self, source: IO[bytes]) -> date | None:
        return self._with_image(source, _exif_date)

    def _with_image(self, source: IO[bytes], use: Callable[[Image.Image], _T]) -> _T:
        with _opened(source) as image:
            return use(image)


@contextmanager
def _opened(source: IO[bytes]) -> Iterator[Image.Image]:
    """Open ``source``, map every decode failure to the domain error, always rewind."""
    try:
        source.seek(0)
        with Image.open(source) as image:
            yield image
    except _DECODE_ERRORS:
        raise ImageProcessingError(getattr(source, "name", "") or "imagem") from None
    finally:
        source.seek(0)


def _flatten(image: Image.Image, target: int) -> Image.Image:
    """First frame, decoded near ``target`` (JPEG draft), upright, alpha on white, in RGB."""
    image.seek(0)
    image.draft("RGB", (target, target))
    upright = ImageOps.exif_transpose(image) or image
    if not _has_alpha(upright):
        return upright.convert("RGB")
    rgba = upright.convert("RGBA")
    background = Image.new("RGB", rgba.size, (255, 255, 255))
    background.paste(rgba, mask=rgba.getchannel("A"))
    return background


def _has_alpha(image: Image.Image) -> bool:
    return image.mode in ("RGBA", "LA", "PA") or (
        image.mode == "P" and "transparency" in image.info
    )


def _to_jpeg(image: Image.Image, quality: int) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue()


def _exif_date(image: Image.Image) -> date | None:
    """``DateTimeOriginal`` from the Exif IFD, else ``DateTime``; anything malformed is None."""
    exif = image.getexif()
    raw = exif.get_ifd(_EXIF_IFD).get(_DATE_TIME_ORIGINAL) or exif.get(_DATE_TIME)
    if not isinstance(raw, str):
        return None
    try:
        return datetime.strptime(raw.strip()[:19], _EXIF_DATE_FORMAT).date()
    except ValueError:
        return None
