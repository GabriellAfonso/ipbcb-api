import logging

from django.utils import timezone

from core.time.clock import Clock
from features.songs.repositories.interfaces import SetlistRepository
from features.songs.services.setlist_rules import purge_cutoffs

logger = logging.getLogger(__name__)


class SetlistPurgeService:
    """Delete setlists past their use (specs/017-sunday-setlist-push FR-028). Idempotent, so a
    missed or doubled daily run is harmless."""

    def __init__(self, setlist_repository: SetlistRepository, clock: Clock) -> None:
        self._setlists = setlist_repository
        self._clock = clock

    def purge_expired(self) -> int:
        """Delete confirmed setlists older than 30 days and unconfirmed ones older than 90,
        counted from the local today (``America/Sao_Paulo``). Returns how many went.

        >>> service.purge_expired()
        3
        """
        confirmed_before, unconfirmed_before = purge_cutoffs(timezone.localdate(self._clock.now()))
        deleted = self._setlists.purge(confirmed_before, unconfirmed_before)
        fields = {
            "deleted": deleted,
            "confirmed_before": confirmed_before.isoformat(),
            "unconfirmed_before": unconfirmed_before.isoformat(),
        }
        logger.info("setlist_purged", extra=fields)
        return deleted
