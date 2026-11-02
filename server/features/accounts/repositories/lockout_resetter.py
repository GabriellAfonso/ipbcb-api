from axes.utils import reset

from core.application.username import normalize_username
from features.accounts.repositories.interfaces import AccountLockoutResetter


class AxesLockoutResetter(AccountLockoutResetter):
    """Clears the failed-attempt lockout of a username, from every client address: the person may
    be locked out on several networks. Normalised because that is the key axes stores attempts
    under (``core.http.lockout``), and a legacy username may not be."""

    def reset(self, username: str) -> None:
        """>>> AxesLockoutResetter().reset("ana")"""
        reset(username=normalize_username(username))
