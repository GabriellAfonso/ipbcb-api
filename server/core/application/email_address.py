"""E-mail address normalisation, shared by every layer that stores or compares a recovery e-mail.

Beside ``username.py`` for the same reason: ``RegisterDTO`` lives in ``core``, which may not import
from ``features``.
"""


def normalize_email_address(value: str) -> str:
    """Return the canonical form of an address: trimmed and lowercased.

    Registration, the profile and the recovery lookup must agree on this, or a person who typed
    "Ana@Example.com" once and "ana@example.com" later could not recover the account.

    >>> normalize_email_address("  Ana@Example.COM ")
    'ana@example.com'
    """
    return value.strip().lower()
