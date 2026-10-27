"""Videos are accepted on their container signature, never on the name the client sent
(specs/023-gallery-videos FR-012, FR-013)."""

from io import BytesIO

import pytest

from core.domain.exceptions import ValidationError
from core.files.video_validation import (
    MAX_VIDEO_BYTES,
    detect_video_extension,
    extension_for_header,
)


def _ftyp(brand: bytes) -> bytes:
    return b"\x00\x00\x00\x18ftyp" + brand + b"\x00\x00\x02\x00isomiso2"


def _upload(content: bytes, name: str = "clip.mp4") -> BytesIO:
    upload = BytesIO(content + b"\x00" * 64)
    upload.name = name
    return upload


class UnreadableSizedUpload(BytesIO):
    """An upload that reports a size and fails if anything reads it: proves the size check
    comes before any read."""

    def __init__(self, size: int) -> None:
        super().__init__()
        self.size = size

    def read(self, *args: object) -> bytes:
        raise AssertionError("an oversized upload must not be read")


class TestAccepted:
    @pytest.mark.parametrize(
        "brand", [b"isom", b"iso2", b"iso6", b"mp41", b"mp42", b"avc1", b"M4V ", b"dash"]
    )
    def test_mp4_brands_are_mp4(self, brand: bytes) -> None:
        assert detect_video_extension(_upload(_ftyp(brand))) == "mp4"

    def test_quicktime_brand_is_mov(self) -> None:
        assert detect_video_extension(_upload(_ftyp(b"qt  "), "IMG_0042.MOV")) == "mov"

    @pytest.mark.parametrize("atom", [b"moov", b"mdat", b"wide", b"free", b"skip"])
    def test_classic_quicktime_first_atom_is_mov(self, atom: bytes) -> None:
        assert detect_video_extension(_upload(b"\x00\x00\x00\x08" + atom + b"\x00" * 8)) == "mov"

    def test_ignores_the_client_filename(self) -> None:
        assert detect_video_extension(_upload(_ftyp(b"qt  "), "clip.mp4")) == "mov"

    def test_rewinds_the_stream(self) -> None:
        upload = _upload(_ftyp(b"isom"))

        detect_video_extension(upload)

        assert upload.tell() == 0

    def test_exactly_the_limit_is_accepted(self) -> None:
        upload = _upload(_ftyp(b"isom"))
        upload.size = MAX_VIDEO_BYTES  # type: ignore[attr-defined]

        assert detect_video_extension(upload) == "mp4"


class TestRefused:
    @pytest.mark.parametrize(
        "content",
        [
            b"\x1a\x45\xdf\xa3" + b"\x00" * 8,  # Matroska / WEBM (EBML)
            b"RIFF\x00\x00\x00\x00AVI ",  # AVI
            b"\xff\xd8\xff\xe0" + b"\x00" * 8,  # JPEG
            b"<html><body>",
        ],
        ids=["mkv-webm", "avi", "jpeg", "html"],
    )
    def test_other_containers_are_refused(self, content: bytes) -> None:
        with pytest.raises(ValidationError, match="Use MP4 ou MOV"):
            detect_video_extension(_upload(content, "clip.mp4"))

    @pytest.mark.parametrize(
        "brand", [b"3gp4", b"3gp5", b"3g2a", b"M4A ", b"M4B ", b"heic", b"mif1", b"avif", b"jp2 "]
    )
    def test_iso_media_that_is_not_mp4_video_is_refused(self, brand: bytes) -> None:
        with pytest.raises(ValidationError, match="Use MP4 ou MOV"):
            detect_video_extension(_upload(_ftyp(brand)))

    def test_a_file_shorter_than_the_header_is_refused(self) -> None:
        assert extension_for_header(b"\x00\x00\x00\x08ftyp") is None

    def test_oversized_is_refused_before_reading(self) -> None:
        with pytest.raises(ValidationError) as caught:
            detect_video_extension(UnreadableSizedUpload(MAX_VIDEO_BYTES + 1))

        assert str(caught.value) == (
            "Vídeo muito grande: 104857601 bytes. O máximo é 104857600 bytes (100 MB)."
        )
