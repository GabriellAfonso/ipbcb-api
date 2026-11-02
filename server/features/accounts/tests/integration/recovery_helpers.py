"""Shared by the recovery e-mail and password recovery API tests (specs/028-password-recovery)."""

import re

from django.core import mail

from conftest import make_user
from features.accounts.models.user import User


def make_recovery_user(
    username: str = "ana",
    recovery_email: str = "ana@example.com",
    password: str = "secret1",  # nosec B107
) -> User:
    """A password account holding a recovery e-mail.

    >>> make_recovery_user().profile.recovery_email
    'ana@example.com'
    """
    user = make_user(username=username, password=password)
    user.profile.recovery_email = recovery_email
    user.profile.save()
    return user


def _last_body() -> str:
    return str(mail.outbox[-1].body)


def code_for(username: str) -> str:
    """The code of ``username`` in the last message sent.

    >>> code_for("ana")
    '123456'
    """
    match = re.search(rf"^{re.escape(username)}: (\d{{6}})$", _last_body(), re.MULTILINE)
    assert match, f"no code for {username!r} in {mail.outbox[-1].body!r}"
    return match.group(1)


def only_code() -> str:
    """The code in the last confirmation message, alone on its line.

    >>> only_code()
    '123456'
    """
    match = re.search(r"^(\d{6})$", _last_body(), re.MULTILINE)
    assert match, f"no code in {mail.outbox[-1].body!r}"
    return match.group(1)


def wrong_code(*codes: str) -> str:
    """A 6-digit code different from all of ``codes``.

    >>> wrong_code("000000")
    '000001'
    """
    return next(c for c in (f"{n:06d}" for n in range(len(codes) + 1)) if c not in codes)
