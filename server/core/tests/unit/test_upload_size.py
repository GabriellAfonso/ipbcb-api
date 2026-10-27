from io import BytesIO

from core.files.upload_size import upload_size


class UnmeasurableUpload(BytesIO):
    """A stream that cannot seek, like a closed or non-seekable upload."""

    def seek(self, *args: object) -> int:
        raise OSError("not seekable")


class TestUploadSize:
    def test_django_size_wins(self) -> None:
        upload = BytesIO(b"12345")
        setattr(upload, "size", 99)

        assert upload_size(upload) == 99

    def test_measures_the_stream_and_keeps_the_position(self) -> None:
        upload = BytesIO(b"12345")
        upload.seek(2)

        assert (upload_size(upload), upload.tell()) == (5, 2)

    def test_unmeasurable_is_none(self) -> None:
        assert upload_size(UnmeasurableUpload(b"12345")) is None
