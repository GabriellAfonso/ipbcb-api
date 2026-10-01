import logging
from uuid import UUID

from core.application.access_service import AccessService
from core.application.dtos.access_dtos import AccessGrantsDTO
from core.application.dtos.worship_dtos import WorshipFlagsDTO
from core.domain.access import Level, Scope
from core.domain.exceptions import NotWorshipMemberError
from core.domain.worship import WORSHIP_MINISTRY_NAME
from core.repositories.interfaces import WorshipMembershipRepository

logger = logging.getLogger(__name__)

# Saving a setlist and registering plays both need this level on this scope; worship membership
# narrows who may act, it never grants a level (constitution; spec 017 FR-002).
SETLIST_SCOPE = Scope.SONGS
SETLIST_LEVEL = Level.MANAGE


class WorshipAccessService:
    """Who is in the worship ministry, and what that lets them do with setlists.

    Shared by ``accounts`` (profile flags) and ``songs`` (save, current read, push recipients),
    so it lives in ``core`` (specs/017-sunday-setlist-push R-01).
    """

    def __init__(
        self, membership_repository: WorshipMembershipRepository, access_service: AccessService
    ) -> None:
        self._membership = membership_repository
        self._access = access_service

    def flags_for(self, user_id: UUID, grants: AccessGrantsDTO) -> WorshipFlagsDTO:
        """>>> service.flags_for(leader.pk, grants)
        WorshipFlagsDTO(is_worship_member=True, can_save_setlist=True)
        """
        is_member = self._membership.is_worship_member(user_id)
        can_save = is_member and grants.allows(SETLIST_SCOPE, SETLIST_LEVEL)
        return WorshipFlagsDTO(is_worship_member=is_member, can_save_setlist=can_save)

    def is_worship_member(self, user_id: UUID) -> bool:
        """>>> service.is_worship_member(leader.pk)
        True
        """
        return self._membership.is_worship_member(user_id)

    def ensure_worship_member(self, user_id: UUID) -> None:
        """Raise ``NotWorshipMemberError`` (403) unless the user is in the worship ministry.

        >>> service.ensure_worship_member(outsider.pk)
        Traceback (most recent call last):
        NotWorshipMemberError: Disponível apenas para o ministério de Louvor.
        """
        if not self.is_worship_member(user_id):
            raise NotWorshipMemberError()

    def setlist_recipients(self) -> set[UUID]:
        """Everyone in the worship ministry — who receives ``setlist_saved``.

        >>> service.setlist_recipients()
        {UUID('...')}
        """
        self._warn_if_ministry_missing()
        return self._membership.worship_member_user_ids()

    def reminder_recipients(self) -> set[UUID]:
        """Worship members who can register plays — who receives ``confirm_plays``.

        >>> service.reminder_recipients()
        {UUID('...')}
        """
        self._warn_if_ministry_missing()
        holders = self._access.user_ids_with_level(SETLIST_SCOPE, SETLIST_LEVEL)
        return holders & self._membership.worship_member_user_ids()

    def _warn_if_ministry_missing(self) -> None:
        # A renamed ministry silently empties every recipient list; this is what makes it show.
        if not self._membership.worship_ministry_exists():
            logger.warning(
                "worship_ministry_missing", extra={"ministry_name": WORSHIP_MINISTRY_NAME}
            )
