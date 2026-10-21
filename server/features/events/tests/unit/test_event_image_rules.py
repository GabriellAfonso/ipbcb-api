import pytest

from core.domain.exceptions import EventImageInvalidError
from features.events.domain.event_image_rules import (
    ensure_event_image_extension,
    ensure_event_image_shape,
)


class TestExtension:
    @pytest.mark.parametrize("extension", ["jpg", "png", "webp"])
    def test_accepts_jpeg_png_webp(self, extension: str) -> None:
        ensure_event_image_extension(extension)

    def test_refuses_gif(self) -> None:
        with pytest.raises(EventImageInvalidError, match="GIF"):
            ensure_event_image_extension("gif")


class TestShape:
    @pytest.mark.parametrize(
        "size", [(1920, 1080), (640, 360), (1000, 563), (4000, 2250), (1280, 720)]
    )
    def test_accepts_16_9_within_tolerance(self, size: tuple[int, int]) -> None:
        ensure_event_image_shape(*size)

    @pytest.mark.parametrize("size", [(1600, 1000), (1080, 1920), (1200, 900), (1920, 1150)])
    def test_refuses_other_ratios_naming_the_received_one(self, size: tuple[int, int]) -> None:
        with pytest.raises(EventImageInvalidError, match=f"{size[0]}x{size[1]}") as caught:
            ensure_event_image_shape(*size)

        assert "16:9" in str(caught.value)

    @pytest.mark.parametrize("size", [(639, 360), (640, 359), (320, 180)])
    def test_refuses_below_the_minimum(self, size: tuple[int, int]) -> None:
        with pytest.raises(EventImageInvalidError, match="640x360"):
            ensure_event_image_shape(*size)

    def test_refuses_above_the_pixel_limit(self) -> None:
        with pytest.raises(EventImageInvalidError, match="megapixels"):
            ensure_event_image_shape(16000, 9000)
