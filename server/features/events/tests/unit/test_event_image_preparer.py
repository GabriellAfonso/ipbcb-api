from io import BytesIO

import pytest

from core.domain.exceptions import EventImageInvalidError
from core.files.imaging.pillow_image_processor import PillowImageProcessor
from features.events.services.event_image_preparer import EventImagePreparer
from features.events.tests.fakes import FakeImageProcessor
from features.events.tests.images import image_bytes


def _upload(content: bytes) -> BytesIO:
    stream = BytesIO(content)
    stream.name = "poster"
    return stream


class TestWithFakeProcessor:
    def test_valid_image_is_fitted_to_1800_by_1200(self) -> None:
        processor = FakeImageProcessor(size=(1200, 800))

        result = EventImagePreparer(processor).prepare(_upload(image_bytes()))

        assert result == FakeImageProcessor.FITTED
        assert processor.fitted_calls == [(1800, 1200, 85)]

    def test_wrong_ratio_is_refused_before_processing(self) -> None:
        processor = FakeImageProcessor(size=(1920, 1080))

        with pytest.raises(EventImageInvalidError, match="3:2"):
            EventImagePreparer(processor).prepare(_upload(image_bytes()))
        assert processor.fitted_calls == []

    def test_processing_failure_becomes_an_image_error(self) -> None:
        processor = FakeImageProcessor(fails=True)

        with pytest.raises(EventImageInvalidError, match="processar"):
            EventImagePreparer(processor).prepare(_upload(image_bytes()))

    def test_not_an_image_is_refused(self) -> None:
        with pytest.raises(EventImageInvalidError, match="Formato inválido"):
            EventImagePreparer(FakeImageProcessor()).prepare(_upload(b"<html></html>"))

    def test_gif_is_refused(self) -> None:
        with pytest.raises(EventImageInvalidError, match="GIF"):
            EventImagePreparer(FakeImageProcessor()).prepare(
                _upload(image_bytes(image_format="GIF"))
            )

    def test_oversized_file_is_refused(self) -> None:
        big = _upload(image_bytes() + b"\0" * (10 * 1024 * 1024))

        with pytest.raises(EventImageInvalidError, match="muito grande"):
            EventImagePreparer(FakeImageProcessor()).prepare(big)


class TestWithPillow:
    def test_ratio_is_measured_as_displayed(self) -> None:
        # Stored 800x1200 (2:3) but tagged to display rotated: shown as 3:2, accepted.
        upload = _upload(image_bytes(size=(800, 1200), orientation=6))

        result = EventImagePreparer(PillowImageProcessor()).prepare(upload)

        assert result[:2] == b"\xff\xd8"

    def test_landscape_pixels_displayed_as_portrait_are_refused(self) -> None:
        upload = _upload(image_bytes(size=(1280, 720), orientation=6))

        with pytest.raises(EventImageInvalidError, match="720x1280"):
            EventImagePreparer(PillowImageProcessor()).prepare(upload)
