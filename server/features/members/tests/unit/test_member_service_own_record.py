"""MemberService.get_own_record (specs/022-access-requests FR-023)."""

from uuid import UUID, uuid4

import pytest

from core.domain.exceptions import MemberNotLinkedError
from features.members.dtos import BirthdayDTO, MemberDTO, OwnMemberRecordDTO
from features.members.services.member_service import MemberService


class FakeOwnRecordRepository:
    """Answers one account's record; every other account is unlinked."""

    def __init__(self, owner: UUID, record: OwnMemberRecordDTO) -> None:
        self.owner = owner
        self.record = record

    def list_active_members(self) -> list[MemberDTO]:
        return []

    def list_birthdays_by_month_range(self, start_month: int, end_month: int) -> list[BirthdayDTO]:
        return []

    def get_own_record(self, user_id: UUID) -> OwnMemberRecordDTO | None:
        return self.record if user_id == self.owner else None


RECORD = OwnMemberRecordDTO(
    id=12,
    name="Ana Souza",
    role=None,
    ministries=[],
    birth_day=None,
    birth_month=None,
    birth_year=None,
    baptism_date=None,
    gender=None,
)


def test_linked_account_gets_its_record() -> None:
    owner = uuid4()
    service = MemberService(FakeOwnRecordRepository(owner, RECORD))
    assert service.get_own_record(owner) == RECORD


def test_unlinked_account_is_told_so() -> None:
    service = MemberService(FakeOwnRecordRepository(uuid4(), RECORD))
    with pytest.raises(MemberNotLinkedError):
        service.get_own_record(uuid4())
