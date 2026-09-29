"""The change feed's cursor: an opaque, versioned encoding of the instant a feed read started.

The app stores it and sends it back, never parses it. Unsigned on purpose: a forged cursor can
only make a member receive gallery data they may already read in full
(specs/014-gallery-trash-sync research R-07).
"""

import base64
import binascii
from datetime import UTC, datetime, timedelta

from features.gallery.domain.trash_rules import CURSOR_OVERLAP, MARK_RETENTION

_VERSION_PREFIX = "v1."
_PAYLOAD_BYTES = 8
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def encode_cursor(issued_at: datetime) -> str:
    """>>> encode_cursor(datetime(2026, 9, 29, tzinfo=UTC))
    'v1.AAZck90e4AA'
    """
    micros = (issued_at - _EPOCH) // timedelta(microseconds=1)
    payload = micros.to_bytes(_PAYLOAD_BYTES, "big")
    return _VERSION_PREFIX + base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_cursor(raw: str) -> datetime | None:
    """The instant a cursor encodes, or None for anything this version did not issue.

    >>> decode_cursor(encode_cursor(datetime(2026, 9, 29, tzinfo=UTC)))
    datetime.datetime(2026, 9, 29, 0, 0, tzinfo=datetime.timezone.utc)
    """
    if not raw.isascii() or not raw.startswith(_VERSION_PREFIX):
        return None
    body = raw.removeprefix(_VERSION_PREFIX)
    try:
        payload = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
    except (binascii.Error, ValueError):
        return None
    if len(payload) != _PAYLOAD_BYTES:
        return None
    return _EPOCH + timedelta(microseconds=int.from_bytes(payload, "big"))


def feed_window_start(since: datetime) -> datetime:
    """Oldest change instant a read with cursor ``since`` returns.

    >>> feed_window_start(datetime(2026, 9, 29, 0, 1, 30, tzinfo=UTC))
    datetime.datetime(2026, 9, 29, 0, 0, tzinfo=datetime.timezone.utc)
    """
    return since - CURSOR_OVERLAP


def requires_full_sync(since: datetime | None, now: datetime) -> bool:
    """True when a sent cursor cannot give a complete delta: unreadable (``None``), from the
    future, or older than the deletion marks reach. An absent cursor is a plain full sync and
    never reaches this function.

    >>> requires_full_sync(None, datetime(2026, 9, 29, tzinfo=UTC))
    True
    """
    if since is None:
        return True
    if since > now + CURSOR_OVERLAP:
        return True
    return since < now - MARK_RETENTION + CURSOR_OVERLAP
