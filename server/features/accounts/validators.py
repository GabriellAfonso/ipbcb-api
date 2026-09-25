"""Username rules.

The username is also a directory name under MEDIA_ROOT (see ``profile_photo_path``), so
the accepted character set is deliberately narrower than Django's
``UnicodeUsernameValidator``: that one accepts ``..`` and every Unicode letter, and both
are unsafe here — ``..`` raises ``SuspiciousFileOperation`` on save, and Unicode letters
allow homoglyph impersonation (Cyrillic "аdmin" against ASCII "admin").

Messages are in Portuguese: they reach the app user through serializer errors.
"""

import re
import unicodedata
from typing import Final

from django.core.exceptions import ValidationError as DjangoValidationError

# Starting and ending alphanumeric is what rejects "..", ".", ".hidden" and "trailing.".
USERNAME_PATTERN: Final = re.compile(r"^[a-z0-9]([a-z0-9._-]*[a-z0-9])?$")

USERNAME_RULE_MESSAGE: Final = (
    "Use apenas letras minúsculas sem acento, números, ponto, hífen e sublinhado, "
    "começando e terminando com letra ou número."
)

_FALLBACK_USERNAME: Final = "usuario"


def is_valid_username(value: str) -> bool:
    """Answer whether ``value`` is safe both as a login and as a directory name.

    >>> is_valid_username("ana.paula")
    True
    """
    return bool(USERNAME_PATTERN.match(value))


def profile_photo_folder(username: str, user_id: str) -> str:
    """Folder under ``profiles/`` that holds this user's photo.

    Falls back to the user id when the username predates the username rules: those rows
    exist, and their usernames may hold path separators or "..". Shared by the upload path
    and the media owner check, so both always agree on which folder is the user's.

    >>> profile_photo_folder("ana.paula", "3f2b...")
    'ana.paula'
    """
    return username if is_valid_username(username) else user_id


def validate_username(value: str) -> None:
    """Raise Django's ``ValidationError`` when the username breaks the rule.

    Call it after normalisation — "ADMIN" is valid once lowercased.

    >>> validate_username("ana.paula")
    """
    if is_valid_username(value):
        return
    raise DjangoValidationError(f"Nome de usuário inválido: '{value}'. {USERNAME_RULE_MESSAGE}")


def sanitize_username(value: str) -> str:
    """Coerce an external identifier into a valid username.

    Used for the Google login path, where the base name comes from the e-mail local part
    and never passes through the register serializer. Accents are transliterated rather
    than dropped, so "joão" becomes "joao" instead of "joo".

    >>> sanitize_username("João.Silva+igreja")
    'joao.silva-igreja'
    """
    decomposed = unicodedata.normalize("NFKD", value.lower())
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii")
    replaced = re.sub(r"[^a-z0-9._-]", "-", ascii_only)
    return replaced.strip("._-") or _FALLBACK_USERNAME
