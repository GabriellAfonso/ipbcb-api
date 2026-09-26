from core.domain.exceptions import MemberNotFoundError
from features.members.dtos import ChangeLogEntryDTO
from features.members.repositories.interfaces import (
    MemberChangeLogRepository,
    MemberRosterRepository,
)


class MemberChangeLogService:
    """Reads a member's edit history. Reads themselves are never recorded (FR-020)."""

    def __init__(
        self,
        change_log_repository: MemberChangeLogRepository,
        roster_repository: MemberRosterRepository,
    ) -> None:
        self._change_log = change_log_repository
        self._roster = roster_repository

    def list_history(self, member_id: int) -> list[ChangeLogEntryDTO]:
        """History entries for ``member_id``, newest first.

        >>> service.list_history(12)[0].field
        'ministries'
        """
        if not self._roster.exists(member_id):
            raise MemberNotFoundError(member_id)
        return self._change_log.list_for_member(member_id)
