"""PillowImageProcessor on real bytes generated in memory (specs/013-gallery-write-api R-04)."""

import io
from datetime import date
from typing import cast

import pytest
from PIL import Image

from core.domain.exceptions import ImageProcessingError
from features.gallery.imaging.pillow_image_processor import PillowImageProcessor

_EXIF_IFD = 0x8769
_ORIENTATION = 0x0112
_DATE_TIME_ORIGINAL = 0x9003


def _encode(image: Image.Image, fmt: str, **save_kwargs: object) -> io.BytesIO:
    buffer = io.BytesIO()
    image.save(buffer, format=fmt, **save_kwargs)
    buffer.seek(0)
    buffer.name = f"test.{fmt.lower()}"
    return buffer


def _jpeg(size: tuple[int, int], color: str = "red", **save_kwargs: object) -> io.BytesIO:
    return _encode(Image.new("RGB", size, color), "JPEG", **save_kwargs)


def _exif(date_original: str | None = None, orientation: int | None = None) -> Image.Exif:
    exif = Image.Exif()
    if orientation is not None:
        exif[_ORIENTATION] = orientation
    if date_original is not None:
        exif.get_ifd(_EXIF_IFD)[_DATE_TIME_ORIGINAL] = date_original
    return exif


def _decode(content: bytes) -> Image.Image:
    return Image.open(io.BytesIO(content))


def _rgb(image: Image.Image, xy: tuple[int, int]) -> tuple[int, int, int]:
    red, green, blue = cast(tuple[int, int, int], image.convert("RGB").getpixel(xy))
    return red, green, blue


PROCESSOR = PillowImageProcessor()


class TestDimensions:
    def test_reads_width_and_height(self) -> None:
        assert PROCESSOR.dimensions(_jpeg((640, 480))) == (640, 480)


class TestBoundedJpeg:
    def test_landscape_is_bounded_by_width(self) -> None:
        result = _decode(PROCESSOR.bounded_jpeg(_jpeg((3000, 2000)), 1000, 85))

        assert result.format == "JPEG"
        assert result.size == (1000, 667)

    def test_portrait_is_bounded_by_height(self) -> None:
        assert _decode(PROCESSOR.bounded_jpeg(_jpeg((2000, 3000)), 1000, 85)).size == (667, 1000)

    def test_small_image_is_never_upscaled(self) -> None:
        assert _decode(PROCESSOR.bounded_jpeg(_jpeg((800, 600)), 1000, 85)).size == (800, 600)

    def test_transparency_becomes_white(self) -> None:
        png = _encode(Image.new("RGBA", (20, 20), (0, 0, 0, 0)), "PNG")

        result = _decode(PROCESSOR.bounded_jpeg(png, 1000, 85))

        assert _rgb(result, (10, 10)) == (255, 255, 255)

    def test_gif_uses_the_first_frame(self) -> None:
        frames = [Image.new("RGB", (30, 30), color) for color in ("blue", "yellow")]
        gif = io.BytesIO()
        frames[0].save(gif, format="GIF", save_all=True, append_images=frames[1:])
        gif.seek(0)

        red, green, blue = _rgb(_decode(PROCESSOR.bounded_jpeg(gif, 1000, 85)), (15, 15))

        assert blue > 200 and red < 60 and green < 60

    def test_exif_orientation_is_applied(self) -> None:
        # Orientation 6: stored landscape, displayed rotated 90 degrees.
        source = _jpeg((300, 200), exif=_exif(orientation=6))

        assert _decode(PROCESSOR.bounded_jpeg(source, 1000, 85)).size == (200, 300)


class TestSquareJpeg:
    @pytest.mark.parametrize("size", [(3000, 2000), (2000, 3000), (500, 300)])
    def test_always_exactly_the_side(self, size: tuple[int, int]) -> None:
        assert _decode(PROCESSOR.square_jpeg(_jpeg(size), 1000, 85)).size == (1000, 1000)

    def test_crop_is_centered(self) -> None:
        image = Image.new("RGB", (300, 100), "red")
        image.paste(Image.new("RGB", (100, 100), "blue"), (100, 0))

        center = _rgb(_decode(PROCESSOR.square_jpeg(_encode(image, "PNG"), 100, 95)), (50, 50))

        assert center[2] > 200 and center[0] < 60


class TestCaptureDate:
    def test_reads_date_time_original(self) -> None:
        source = _jpeg((10, 10), exif=_exif(date_original="2026:03:14 09:30:00"))

        assert PROCESSOR.capture_date(source) == date(2026, 3, 14)

    def test_none_without_exif(self) -> None:
        assert PROCESSOR.capture_date(_jpeg((10, 10))) is None

    def test_malformed_date_is_none(self) -> None:
        source = _jpeg((10, 10), exif=_exif(date_original="0000:00:00 00:00:00"))

        assert PROCESSOR.capture_date(source) is None


class TestFailures:
    def test_truncated_bytes_raise_the_domain_error(self) -> None:
        truncated = io.BytesIO(_jpeg((400, 400)).getvalue()[:300])
        truncated.name = "broken.jpg"

        with pytest.raises(ImageProcessingError, match="broken.jpg"):
            PROCESSOR.bounded_jpeg(truncated, 1000, 85)

    def test_not_an_image_raises_the_domain_error(self) -> None:
        with pytest.raises(ImageProcessingError):
            PROCESSOR.dimensions(io.BytesIO(b"not an image"))


class TestStreamIsRewound:
    def test_after_each_call(self) -> None:
        source = _jpeg((50, 50))

        PROCESSOR.bounded_jpeg(source, 1000, 85)
        assert source.tell() == 0
        PROCESSOR.capture_date(source)
        assert source.tell() == 0
