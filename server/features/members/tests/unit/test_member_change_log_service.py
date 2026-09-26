from datetime import datetime, timezone

import pytest

from core.domain.exceptions import MemberNotFoundError
from features.members.dtos import ChangeLogEntryDTO
from features.members.services.member_change_log_service import MemberChangeLogService
from features.members.tests.fakes import (
    FakeMemberChangeLogRepository,
    FakeMemberRosterRepository,
)

ENTRY = ChangeLogEntryDTO(
    id=1,
    editor=None,
    field="created",
    old_value=None,
    new_value=None,
    changed_at=datetime(2026, 9, 25, tzinfo=timezone.utc),
)


class TestListHistory:
    def test_returns_the_repository_entries(self) -> None:
        roster = FakeMemberRosterRepository()
        member = roster.add("Ana")
        service = MemberChangeLogService(FakeMemberChangeLogRepository([ENTRY]), roster)

        assert service.list_history(member.id) == [ENTRY]

    def test_unknown_member_raises(self) -> None:
        service = MemberChangeLogService(
            FakeMemberChangeLogRepository(), FakeMemberRosterRepository()
        )

        with pytest.raises(MemberNotFoundError):
            service.list_history(5)
