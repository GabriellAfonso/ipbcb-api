"""Content-based validation for uploaded gallery videos.

Only the container signature is read — the first 12 bytes. The server never decodes, probes or
transcodes a video: the media team posts playable files and the app checks codecs before sending
(specs/023-gallery-videos FR-013, FR-014, research R-03). As for images, the filename and the
declared Content-Type are never trusted.

Messages are in Portuguese on purpose: they reach the uploader through the canonical error body.
"""

from typing import IO, Final

from core.domain.exceptions import ValidationError
from core.files.upload_size import upload_size

# One constant (spec FR-012). nginx allows 110M at /ipbcb/ for the poster and form fields.
MAX_VIDEO_BYTES: Final = 100 * 1024 * 1024

_HEADER_BYTES: Final = 12
_QUICKTIME_BRAND: Final = b"qt  "
# Classic QuickTime files may start with any of these atoms instead of an `ftyp` box.
_QUICKTIME_FIRST_ATOMS: Final = frozenset({b"moov", b"mdat", b"wide", b"free", b"skip"})
# ISO base media files that are not MP4 video: 3GPP, audio-only, still images. Brands are
# compared on their first three bytes for 3GPP, which numbers its brands (3gp4, 3gp5, 3g2a…).
_REFUSED_BRAND_PREFIXES: Final = (b"3gp", b"3g2")
_REFUSED_BRANDS: Final = frozenset(
    {
        b"M4A ",
        b"M4B ",
        b"M4P ",
        b"F4A ",
        b"F4B ",
        b"heic",
        b"heix",
        b"heim",
        b"heis",
        b"hevc",
        b"hevx",
        b"mif1",
        b"msf1",
        b"avif",
        b"avis",
        b"jp2 ",
        b"crx ",
    }
)

_UNSUPPORTED_MESSAGE: Final = "Formato de vídeo não suportado. Use MP4 ou MOV."


def detect_video_extension(upload: IO[bytes], max_bytes: int = MAX_VIDEO_BYTES) -> str:
    """Return ``"mp4"`` or ``"mov"`` for ``upload``, or raise ``ValidationError``.

    The size is checked before any byte is read; the stream is left rewound.

    >>> detect_video_extension(open("culto.mp4", "rb"))
    'mp4'
    """
    _reject_oversized(upload, max_bytes)
    extension = extension_for_header(_read_header(upload))
    if extension is None:
        raise ValidationError(_UNSUPPORTED_MESSAGE)
    return extension


def extension_for_header(header: bytes) -> str | None:
    """Extension of a video whose file starts with ``header``, or ``None`` when it is neither
    MP4 nor MOV.

    >>> extension_for_header(b"\\x00\\x00\\x00\\x14ftypqt  ")
    'mov'
    """
    if len(header) < _HEADER_BYTES:
        return None
    box_type, brand = header[4:8], header[8:12]
    if box_type in _QUICKTIME_FIRST_ATOMS:
        return "mov"
    if box_type != b"ftyp":
        return None
    if brand == _QUICKTIME_BRAND:
        return "mov"
    if brand in _REFUSED_BRANDS or brand.startswith(_REFUSED_BRAND_PREFIXES):
        return None
    return "mp4"


def _reject_oversized(upload: IO[bytes], max_bytes: int) -> None:
    size = upload_size(upload)
    if size is None or size <= max_bytes:
        return
    raise ValidationError(
        f"Vídeo muito grande: {size} bytes. O máximo é {max_bytes} bytes "
        f"({max_bytes // (1024 * 1024)} MB)."
    )


def _read_header(upload: IO[bytes]) -> bytes:
    try:
        upload.seek(0)
        return upload.read(_HEADER_BYTES)
    finally:
        upload.seek(0)
