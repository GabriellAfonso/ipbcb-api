"""Pure rules of the client upload id sent with a photo upload.

No I/O: every refusal here comes before the id is looked up or anything is stored
(specs/016-photo-upload-idempotency FR-005, research R-05).
"""

import re

from core.domain.exceptions import ClientUploadNeedsOneFileError, InvalidClientUploadIdError

# Room for a UUID (36 characters) and other opaque formats, without whitespace or separators
# that could hide a mismatch between two retries of the same photo.
CLIENT_UPLOAD_ID_MAX_LENGTH = 64
CLIENT_UPLOAD_ID_SHAPE = f"1-{CLIENT_UPLOAD_ID_MAX_LENGTH} characters of A-Z, a-z, 0-9, '-' or '_'"

# ASCII only on purpose: str.isalnum() would accept any Unicode letter.
_ALLOWED_CHARACTER = re.compile(r"[A-Za-z0-9_-]")


def ensure_valid_client_upload(client_upload_id: str, file_count: int) -> None:
    """Refuse an id of the wrong shape, or one sent with anything but exactly one file.

    >>> ensure_valid_client_upload("3f2a9c1e-7b4d-4e8a-9f10-2c6b5d7e8a90", 1)
    """
    problem = _shape_problem(client_upload_id)
    if problem is not None:
        raise InvalidClientUploadIdError(
            client_upload_id[:CLIENT_UPLOAD_ID_MAX_LENGTH], problem, CLIENT_UPLOAD_ID_SHAPE
        )
    if file_count != 1:
        raise ClientUploadNeedsOneFileError(file_count)


def _shape_problem(client_upload_id: str) -> str | None:
    """What is wrong with the id, phrased for the error message; ``None`` when it is valid."""
    if not client_upload_id:
        return "got an empty value"
    if len(client_upload_id) > CLIENT_UPLOAD_ID_MAX_LENGTH:
        return f"got {len(client_upload_id)} characters"
    for position, character in enumerate(client_upload_id):
        if not _ALLOWED_CHARACTER.fullmatch(character):
            return f"got {character!r} at position {position}"
    return None
