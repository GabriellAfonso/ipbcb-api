from core.time.clock import Clock
from features.accounts.repositories.interfaces import EmailCodeRepository


class EmailCodePurgeService:
    """Removes expired codes and stale send ledgers (specs/028-password-recovery FR-019)."""

    def __init__(self, email_code_repository: EmailCodeRepository, clock: Clock) -> None:
        self._codes = email_code_repository
        self._clock = clock

    def purge_expired(self) -> int:
        """Return how many rows went.

        >>> service.purge_expired()
        3
        """
        return self._codes.purge_expired(self._clock.now())
