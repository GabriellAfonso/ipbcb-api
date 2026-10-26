"""Real encoded images for event upload tests: validation decodes content, so bytes must be real."""

from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

_ORIENTATION = 0x0112


def image_bytes(
    size: tuple[int, int] = (1200, 800),
    image_format: str = "JPEG",
    orientation: int | None = None,
) -> bytes:
    buffer = BytesIO()
    mode = "RGBA" if image_format == "PNG" else "RGB"
    image = Image.new(mode, size, color=(30, 90, 200))
    if orientation is None:
        image.save(buffer, format=image_format)
    else:
        exif = Image.Exif()
        exif[_ORIENTATION] = orientation
        image.save(buffer, format=image_format, exif=exif)
    return buffer.getvalue()


def image_upload(
    size: tuple[int, int] = (1200, 800),
    image_format: str = "JPEG",
    filename: str = "poster.jpg",
    orientation: int | None = None,
) -> SimpleUploadedFile:
    return SimpleUploadedFile(filename, image_bytes(size, image_format, orientation))


def fake_image_upload() -> SimpleUploadedFile:
    """Text dressed up as a PNG: refused by decoded content, whatever the name says."""
    return SimpleUploadedFile("poster.png", b"<html>not an image</html>", content_type="image/png")
