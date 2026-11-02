"""Rules of the e-mail codes (specs/028-password-recovery): generation, keyed hashing and the
per-address send limit. Pure: no ORM and no clock of its own."""

import math
import secrets
from collections.abc import Iterable
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Final

from django.utils.crypto import constant_time_compare, salted_hmac

CODE_LIFETIME: Final = timedelta(minutes=15)
MAX_WRONG_ATTEMPTS: Final = 5
SEND_MIN_INTERVAL: Final = timedelta(minutes=1)
SEND_WINDOW: Final = timedelta(hours=1)
SEND_MAX_PER_WINDOW: Final = 5

_CODE_SPACE: Final = 1_000_000
_CODE_SALT: Final = "features.accounts.email_code"
_ADDRESS_SALT: Final = "features.accounts.email_address"


class EmailCodePurpose(StrEnum):
    RECOVERY = "recovery"
    CONFIRMATION = "confirmation"


def generate_codes(count: int) -> list[str]:
    """Return ``count`` different 6-digit codes from a cryptographic source. Different because
    accounts sharing an address get their codes in one message, and the code alone tells the
    accounts apart on confirmation.

    >>> len(set(generate_codes(3)))
    3
    """
    codes: set[str] = set()
    while len(codes) < count:
        codes.add(f"{secrets.randbelow(_CODE_SPACE):06d}")
    return list(codes)


def code_digest(purpose: EmailCodePurpose, address: str, code: str) -> str:
    """Keyed hash of a code. Six digits fall instantly to an unkeyed hash if the table leaks; the
    key stays outside the database. Purpose and address are bound in, so a code of one purpose
    cannot be replayed for the other (research R-08).

    >>> len(code_digest(EmailCodePurpose.RECOVERY, "ana@example.com", "123456"))
    64
    """
    value = f"{purpose.value}:{address}:{code}"
    return salted_hmac(_CODE_SALT, value, algorithm="sha256").hexdigest()


def digests_match(stored: str, candidate: str) -> bool:
    """Constant-time comparison, so response time says nothing about a guess.

    >>> digests_match("abc", "abc")
    True
    """
    return constant_time_compare(stored, candidate)


def address_key(address: str) -> str:
    """Keyed hash identifying an address in the send ledger. Anyone can post any address, so the
    table must not become a readable list of what they typed (research R-04).

    >>> len(address_key("ana@example.com"))
    64
    """
    return salted_hmac(_ADDRESS_SALT, address, algorithm="sha256").hexdigest()


def sends_inside_window(sends: Iterable[datetime], now: datetime) -> list[datetime]:
    """The send moments still counting against the limit, oldest first.

    >>> sends_inside_window([now - timedelta(hours=2)], now)
    []
    """
    return sorted(moment for moment in sends if moment > now - SEND_WINDOW)


def send_wait_seconds(recent_sends: list[datetime], now: datetime) -> int:
    """Seconds until the address may receive another message; 0 when it may now. Takes the output
    of ``sends_inside_window``. Rolling on purpose: a fixed window lets 9 messages through in 9
    minutes across its boundary (research R-03).

    >>> send_wait_seconds([], now)
    0
    """
    if not recent_sends:
        return 0
    until_interval = recent_sends[-1] + SEND_MIN_INTERVAL - now
    until_window = timedelta(0)
    if len(recent_sends) >= SEND_MAX_PER_WINDOW:
        until_window = recent_sends[-SEND_MAX_PER_WINDOW] + SEND_WINDOW - now
    return max(0, math.ceil(max(until_interval, until_window).total_seconds()))
