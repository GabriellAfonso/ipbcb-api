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
        "size", [(1800, 1200), (600, 400), (1000, 667), (6000, 4000), (1200, 800)]
    )
    def test_accepts_3_2_within_tolerance(self, size: tuple[int, int]) -> None:
        ensure_event_image_shape(*size)

    @pytest.mark.parametrize("size", [(1920, 1080), (1200, 1800), (1200, 900), (1600, 1000)])
    def test_refuses_other_ratios_naming_the_received_one(self, size: tuple[int, int]) -> None:
        with pytest.raises(EventImageInvalidError, match=f"{size[0]}x{size[1]}") as caught:
            ensure_event_image_shape(*size)

        assert "3:2" in str(caught.value)

    @pytest.mark.parametrize("size", [(599, 400), (600, 399), (300, 200)])
    def test_refuses_below_the_minimum(self, size: tuple[int, int]) -> None:
        with pytest.raises(EventImageInvalidError, match="600x400"):
            ensure_event_image_shape(*size)

    def test_refuses_above_the_pixel_limit(self) -> None:
        with pytest.raises(EventImageInvalidError, match="megapixels"):
            ensure_event_image_shape(9000, 6000)
