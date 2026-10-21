from uuid import UUID

from core.domain.exceptions import MemberNotLinkedError
from features.members.dtos import BirthdayDTO, MemberDTO, OwnMemberRecordDTO
from features.members.repositories.interfaces import MemberRepository


class MemberService:
    def __init__(self, repository: MemberRepository) -> None:
        self._repository = repository

    def list_active_members(self) -> list[MemberDTO]:
        """Return all active members.

        >>> service.list_active_members()
        [MemberDTO(id=1, name='Alice'), ...]
        """
        return self._repository.list_active_members()

    def list_birthdays_by_month_range(self, start_month: int, end_month: int) -> list[BirthdayDTO]:
        """Return members with birthdays in the given month range.

        >>> service.list_birthdays_by_month_range(1, 6)
        [BirthdayDTO(name='Alice', birth_month=1, birth_day=5), ...]
        """
        return self._repository.list_birthdays_by_month_range(start_month, end_month)

    def get_own_record(self, user_id: UUID) -> OwnMemberRecordDTO:
        """The caller's own roll record (specs/022-access-requests FR-023).

        >>> service.get_own_record(ana.pk).role
        'Diaconisa'
        """
        record = self._repository.get_own_record(user_id)
        if record is None:
            raise MemberNotLinkedError()
        return record
