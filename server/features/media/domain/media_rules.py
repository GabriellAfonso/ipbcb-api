"""Access rules for files under MEDIA_ROOT: which folder is readable by whom, which paths
are acceptable at all, and which content type a file is served with.

Pure functions, no I/O — the filesystem lives behind ``MediaFileRepository``. Full design in
``specs/009-protected-media-access/``.
"""

from collections.abc import Mapping
from enum import Enum
from types import MappingProxyType

from core.domain.exceptions import MediaPathRejectedError


class MediaAudience(Enum):
    MEMBER = "member"
    MEMBERS_SCOPE = "members_scope"


class MediaAccessOutcome(Enum):
    ALLOWED = "allowed"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    REJECTED = "rejected"
    UNRULED = "unruled"
    # A gallery file of a trashed item, refused to a member (specs/014-gallery-trash-sync).
    TRASHED = "trashed"


# Default deny: a folder missing here is unreadable by everyone, so a new upload location
# fails closed until someone writes its rule (and its spec).
FOLDER_RULES: Mapping[str, MediaAudience] = MappingProxyType(
    {
        # Members; files of trashed items only with `owner` on `gallery` (spec 014).
        "gallery": MediaAudience.MEMBER,
        "profiles": MediaAudience.MEMBER,
        # Member photos: readable with `view` on the `members` scope — Admin and Liderança,
        # never Mídia (specs/012-feature-role-permissions FR-017).
        "members": MediaAudience.MEMBERS_SCOPE,
    }
)

# Explicit on purpose: nginx keeps an upstream Content-Type, and without one it would guess
# from the extension. Gallery photos uploaded before feature 013 keep their original filename,
# so an image/HTML polyglot named "x.html" would otherwise be served as text/html on our origin.
# Later uploads are stored as "{uuid}.{ext}" with the extension of the decoded format.
_CONTENT_TYPES: Mapping[str, str] = MappingProxyType(
    {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
        "gif": "image/gif",
    }
)
_FALLBACK_CONTENT_TYPE = "application/octet-stream"
_FORBIDDEN_SEGMENTS = frozenset({"", ".", ".."})


def audience_for_folder(folder: str) -> MediaAudience | None:
    """Audience allowed to read ``folder``, or None when the folder has no rule.

    >>> audience_for_folder("gallery")
    <MediaAudience.MEMBER: 'member'>
    """
    return FOLDER_RULES.get(folder)


def is_own_profile_file(path: str, own_profile_folder: str | None) -> bool:
    """Answer whether ``path`` is a file inside the caller's own ``profiles/`` folder.

    Expects a path already accepted by ``validate_media_path``. A bare folder
    (``profiles/ana.paula``) is not a file, so it never counts as owned.

    >>> is_own_profile_file("profiles/ana.paula/6f1c2d.png", "ana.paula")
    True
    """
    if own_profile_folder is None:
        return False
    segments = path.split("/")
    return len(segments) >= 3 and segments[0] == "profiles" and segments[1] == own_profile_folder


def first_segment(path: str) -> str:
    """>>> first_segment("gallery/retiro/x.jpg")
    'gallery'
    """
    return path.split("/", 1)[0]


def content_type_for(path: str) -> str:
    """Content type to serve ``path`` with, from a fixed image allow-list.

    >>> content_type_for("gallery/a/x.JPG")
    'image/jpeg'
    """
    _, dot, extension = path.rpartition(".")
    if not dot:
        return _FALLBACK_CONTENT_TYPE
    return _CONTENT_TYPES.get(extension.lower(), _FALLBACK_CONTENT_TYPE)


def validate_media_path(requested_path: str) -> str:
    """Return ``requested_path`` unchanged, or raise ``MediaPathRejectedError``.

    Validates, never normalizes: nothing is collapsed, so the string that is checked is the
    string that is served. ``gallery/../members/x.jpg`` is rejected, not re-judged.

    >>> validate_media_path("gallery/retiro/IMG_0042.jpg")
    'gallery/retiro/IMG_0042.jpg'
    """
    if _has_forbidden_character(requested_path):
        raise MediaPathRejectedError(requested_path)
    segments = requested_path.split("/")
    if len(segments) < 2 or any(segment in _FORBIDDEN_SEGMENTS for segment in segments):
        raise MediaPathRejectedError(requested_path)
    return requested_path


def _has_forbidden_character(path: str) -> bool:
    """Backslash (Windows separator), NUL/control characters, and "%" — the path arrives
    decoded once, so a leftover "%" is a second encoding layer. No stored file has one:
    Django's get_valid_filename strips it from upload names."""
    return any(ch in "\\%" or ord(ch) < 0x20 or ord(ch) == 0x7F for ch in path)
