from typing import IO

from core.domain.exceptions import EventImageInvalidError, ImageProcessingError, ValidationError
from core.files.image_validation import detect_image_extension
from core.files.imaging.interfaces import ImageProcessor
from features.events.domain.event_image_rules import (
    JPEG_QUALITY,
    MAX_EVENT_IMAGE_BYTES,
    MAX_HEIGHT,
    MAX_WIDTH,
    ensure_event_image_extension,
    ensure_event_image_shape,
)


class EventImagePreparer:
    """Turns an uploaded file into the JPEG an event stores, or refuses it on the ``image`` field.

    Cheap checks first (size, decoded format, header dimensions), so nothing is decoded in full
    before it is known to be acceptable (specs/020-church-events research R-04).
    """

    def __init__(self, image_processor: ImageProcessor) -> None:
        self._processor = image_processor

    def prepare(self, upload: IO[bytes]) -> bytes:
        """Validated, upright JPEG fitted within 1800 x 1200.

        >>> preparer.prepare(open("poster-3x2.png", "rb"))[:2]
        b'\\xff\\xd8'
        """
        try:
            self._validate(upload)
            return self._processor.fitted_jpeg(upload, MAX_WIDTH, MAX_HEIGHT, JPEG_QUALITY)
        except ImageProcessingError:
            raise EventImageInvalidError(
                "Não foi possível processar a imagem enviada. Envie um JPEG, PNG ou WEBP válido."
            ) from None

    def _validate(self, upload: IO[bytes]) -> None:
        try:
            extension = detect_image_extension(upload, MAX_EVENT_IMAGE_BYTES)
        except ValidationError as exc:
            # Core validation speaks for any upload; here it belongs to the "image" field.
            raise EventImageInvalidError(str(exc)) from None
        ensure_event_image_extension(extension)
        ensure_event_image_shape(*self._processor.upright_dimensions(upload))
