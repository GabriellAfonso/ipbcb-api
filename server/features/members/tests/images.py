"""Real encoded images for upload tests: the validator decodes content, so bytes must be real."""

from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image


def image_bytes(image_format: str = "JPEG") -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (4, 4), color=(200, 30, 30)).save(buffer, format=image_format)
    return buffer.getvalue()


def image_upload(image_format: str = "JPEG", filename: str = "ana-souza.jpg") -> SimpleUploadedFile:
    return SimpleUploadedFile(filename, image_bytes(image_format))


def fake_image_upload() -> SimpleUploadedFile:
    """Text dressed up as a PNG: rejected by decoded content, whatever the name says."""
    return SimpleUploadedFile("photo.png", b"<html>not an image</html>", content_type="image/png")
