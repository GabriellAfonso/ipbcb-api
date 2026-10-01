import logging
from datetime import date
from uuid import UUID

from django.utils import timezone

from core.application.dtos.push_dtos import PushMessage
from core.application.push_service import PushService
from core.application.worship_access_service import WorshipAccessService
from core.domain.exceptions import SetlistNotFoundError, SongsNotFoundError
from core.domain.push import PushMessageType
from core.time.clock import Clock
from features.songs.repositories.interfaces import SetlistRepository, SongLookup
from features.songs.services.setlist_rules import ensure_sunday, ensure_unique_positions
from features.songs.setlist_dtos import SetlistDTO, SetlistItemInput

logger = logging.getLogger(__name__)


class SetlistService:
    """Save and read Sunday setlists (specs/017-sunday-setlist-push).

    The scope level (``manage`` on ``songs``) is the view's permission class; worship
    membership, which narrows it, is checked here.
    """

    def __init__(
        self,
        setlist_repository: SetlistRepository,
        song_repository: SongLookup,
        worship_access_service: WorshipAccessService,
        push_service: PushService,
        clock: Clock,
    ) -> None:
        self._setlists = setlist_repository
        self._songs = song_repository
        self._worship = worship_access_service
        self._push = push_service
        self._clock = clock

    def save(self, author_id: UUID, day: date, items: list[SetlistItemInput]) -> SetlistDTO:
        """Create or replace the setlist of ``day``, then push ``setlist_saved`` to the worship
        ministry. The push runs after the save committed and never fails it (R-07).

        >>> service.save(leader.pk, date(2026, 10, 4), [SetlistItemInput(song_id=1, ...)])
        SetlistDTO(date=datetime.date(2026, 10, 4), ...)
        """
        self._worship.ensure_worship_member(author_id)
        ensure_sunday(day)
        ensure_unique_positions(items)
        self._ensure_songs_exist(items)
        setlist, replaced = self._setlists.replace(day, author_id, items, self._clock.now())
        logger.info("setlist_saved", extra=_saved_fields(setlist, author_id, replaced))
        message = PushMessage(type=PushMessageType.SETLIST_SAVED, date=day)
        self._push.notify(self._worship.setlist_recipients(), message)
        return setlist

    def current(self) -> SetlistDTO | None:
        """Earliest setlist from today on (``America/Sao_Paulo``), or ``None``.

        >>> service.current().date
        datetime.date(2026, 10, 4)
        """
        return self._setlists.current(self._today())

    def by_date(self, day: date) -> SetlistDTO:
        """>>> service.by_date(date(2026, 10, 4)).date
        datetime.date(2026, 10, 4)
        """
        setlist = self._setlists.get_by_date(day)
        if setlist is None:
            raise SetlistNotFoundError(day)
        return setlist

    def pending(self) -> list[SetlistDTO]:
        """Setlists whose Sunday has come with no played songs registered, newest first.

        >>> service.pending()
        [SetlistDTO(date=datetime.date(2026, 9, 27), ...)]
        """
        return self._setlists.pending(self._today())

    def _ensure_songs_exist(self, items: list[SetlistItemInput]) -> None:
        song_ids = {item.song_id for item in items}
        found = self._songs.get_songs_in_bulk(song_ids)
        missing = sorted(song_id for song_id in song_ids if song_id not in found)
        if missing:
            raise SongsNotFoundError(missing)

    def _today(self) -> date:
        return timezone.localdate(self._clock.now())


def _saved_fields(setlist: SetlistDTO, author_id: UUID, replaced: bool) -> dict[str, object]:
    return {
        "setlist_date": setlist.date.isoformat(),
        "user_id": str(author_id),
        "item_count": len(setlist.items),
        "replaced": replaced,
    }
