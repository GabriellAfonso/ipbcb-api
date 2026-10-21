"""The project's own interface to image processing (CLAUDE.md §7: third-party libraries behind a
thin interface). Services depend on this Protocol; only the implementation imports Pillow."""

from datetime import date
from typing import IO, Protocol


class ImageProcessor(Protocol):
    """Derivatives and metadata of an already validated image.

    Every method raises ``ImageProcessingError`` when the image cannot be decoded, and leaves
    ``source`` rewound so the caller can read it again.
    """

    def dimensions(self, source: IO[bytes]) -> tuple[int, int]:
        """(width, height) from the header, without decoding the pixels.

        >>> processor.dimensions(open("photo.jpg", "rb"))
        (4032, 3024)
        """
        ...

    def upright_dimensions(self, source: IO[bytes]) -> tuple[int, int]:
        """(width, height) as displayed: swapped when the EXIF orientation turns the image by
        90 degrees. Header only, no pixel decode (specs/020-church-events R-03).

        >>> processor.upright_dimensions(open("portrait_tagged_rotate_90.jpg", "rb"))
        (3024, 4032)
        """
        ...

    def fitted_jpeg(
        self, source: IO[bytes], max_width: int, max_height: int, quality: int
    ) -> bytes:
        """JPEG fitting inside ``max_width`` x ``max_height``, aspect kept, never upscaled,
        upright, alpha flattened on white (specs/020-church-events R-02).

        >>> processor.fitted_jpeg(open("poster.png", "rb"), 1920, 1080, 85)[:2]
        b'\\xff\\xd8'
        """
        ...

    def bounded_jpeg(self, source: IO[bytes], longest_side: int, quality: int) -> bytes:
        """JPEG whose longest side is at most ``longest_side``, aspect kept, never upscaled.

        >>> processor.bounded_jpeg(open("photo.jpg", "rb"), 1000, 85)[:2]
        b'\\xff\\xd8'
        """
        ...

    def square_jpeg(self, source: IO[bytes], side: int, quality: int) -> bytes:
        """JPEG of exactly ``side`` x ``side``, center-cropped.

        >>> processor.square_jpeg(open("photo.jpg", "rb"), 1000, 85)[:2]
        b'\\xff\\xd8'
        """
        ...

    def capture_date(self, source: IO[bytes]) -> date | None:
        """Date the photo was taken according to its EXIF, or None.

        >>> processor.capture_date(open("photo.jpg", "rb"))
        datetime.date(2026, 3, 14)
        """
        ...
