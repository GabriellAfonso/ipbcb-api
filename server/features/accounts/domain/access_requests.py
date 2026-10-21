"""Access requests: kinds, states, limits and the pure rules between them
(specs/022-access-requests). No Django import here.
"""

from datetime import datetime, timedelta
from enum import StrEnum

MESSAGE_MAX_LENGTH = 1000
DENIAL_REASON_MAX_LENGTH = 500
# One request of any type per rolling window (spec FR-007).
REQUEST_INTERVAL = timedelta(hours=24)


class AccessRequestType(StrEnum):
    """The value is the wire name."""

    ACCESS = "access"
    DATA_CORRECTION = "data_correction"


class AccessRequestStatus(StrEnum):
    """``approved`` on a ``data_correction`` request means "resolved"."""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


class AccessStatus(StrEnum):
    """What the profile card shows: Liberado / Aguardando / Não liberado."""

    GRANTED = "granted"
    PENDING = "pending"
    NONE = "none"


def access_status(member_access: bool, access_pending: bool) -> AccessStatus:
    """>>> access_status(False, True)
    <AccessStatus.PENDING: 'pending'>
    """
    if member_access:
        return AccessStatus.GRANTED
    return AccessStatus.PENDING if access_pending else AccessStatus.NONE


def seconds_until_next_request(last_created_at: datetime | None, now: datetime) -> int:
    """Whole seconds before the account may ask again; 0 when it may ask now. Rounded up, so a
    client that waits exactly this long is never refused.

    >>> seconds_until_next_request(asked_at, asked_at + timedelta(hours=23))
    3600
    """
    if last_created_at is None:
        return 0
    remaining = last_created_at + REQUEST_INTERVAL - now
    if remaining <= timedelta(0):
        return 0
    return int(-(-remaining.total_seconds() // 1))


def clean_text(value: str | None) -> str | None:
    """Trimmed text, or None when nothing is left.

    >>> clean_text("   ")
    """
    if value is None:
        return None
    return value.strip() or None


class ProfileListFilter(StrEnum):
    """The two tabs of "Perfis": Pendentes and Todos."""

    PENDING = "pending"
    ALL = "all"
