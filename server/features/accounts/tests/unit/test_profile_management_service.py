"""ProfileManagementService on fakes (specs/022-access-requests US2, US3)."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from core.domain.exceptions import (
    AccessRequestNotFoundError,
    AccessRequestNotPendingError,
    ManagedAccountNotFoundError,
    ProfileStatusFilterError,
)
from core.domain.push import PushMessageType
from features.accounts.domain.access_requests import (
    AccessRequestStatus,
    AccessRequestType,
    ProfileListFilter,
)
from features.accounts.dtos import ManagedAccountDTO, ManagedAccountPatchDTO
from features.accounts.services.profile_management_service import (
    ProfileManagementService,
    parse_list_filter,
)
from features.accounts.tests.access_fakes import (
    FakeAccessRequestRepository,
    FakeManagedAccountRepository,
    FixedClock,
    RecordingPushNotifier,
)

NOW = datetime(2026, 10, 21, 12, tzinfo=UTC)

# approve() opens a transaction, so the test database must be reachable (no rows are written).
pytestmark = pytest.mark.django_db


class Setup:
    def __init__(self) -> None:
        self.clock = FixedClock(NOW)
        self.requests = FakeAccessRequestRepository(self.clock)
        self.accounts = FakeManagedAccountRepository(self.requests)
        self.push = RecordingPushNotifier()
        self.service = ProfileManagementService(self.requests, self.accounts, self.push, self.clock)
        self.leader = uuid4()
        self.ana = self.account()

    def account(self, member_access: bool = False) -> UUID:
        user_id = uuid4()
        self.accounts.accounts[user_id] = ManagedAccountDTO(
            id=user_id,
            name="Ana",
            username=f"u{user_id.hex[:6]}",
            photo_path=None,
            member_access=member_access,
            access_via_role=False,
            access_requests_blocked=False,
            member=None,
            date_joined=NOW,
        )
        return user_id


@pytest.fixture
def setup() -> Setup:
    return Setup()


class TestListFilter:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            (None, ProfileListFilter.ALL),
            ("all", ProfileListFilter.ALL),
            ("pending", ProfileListFilter.PENDING),
        ],
    )
    def test_known_values(self, raw: str | None, expected: ProfileListFilter) -> None:
        assert parse_list_filter(raw) is expected

    def test_unknown_value(self) -> None:
        with pytest.raises(ProfileStatusFilterError):
            parse_list_filter("old")

    def test_pending_tab_lists_only_accounts_with_a_pending_request(self, setup: Setup) -> None:
        setup.account()
        setup.requests.add(setup.ana, AccessRequestType.ACCESS)
        assert [a.id for a in setup.service.list_accounts("pending")] == [setup.ana]
        assert len(setup.service.list_accounts(None)) == 2


class TestApprove:
    def test_access_sets_the_flag_and_notifies_the_requester(self, setup: Setup) -> None:
        request = setup.requests.add(setup.ana, AccessRequestType.ACCESS)
        account = setup.service.approve(request.id, setup.leader)
        assert account.member_access is True
        assert account.access_granted_by is not None
        assert account.access_granted_by.id == setup.leader
        assert account.access_granted_at == NOW
        assert account.requests[0].status is AccessRequestStatus.APPROVED
        assert account.requests[0].decided_at == NOW
        recipients, message = setup.push.sent[0]
        assert recipients == {setup.ana}
        assert message.type is PushMessageType.ACCESS_REQUEST_APPROVED

    def test_access_for_a_flagged_account_keeps_the_earlier_grant(self, setup: Setup) -> None:
        flagged = setup.account(member_access=True)
        request = setup.requests.add(flagged, AccessRequestType.ACCESS)
        account = setup.service.approve(request.id, setup.leader)
        assert account.member_access is True
        assert account.access_granted_by is None

    def test_correction_is_only_closed(self, setup: Setup) -> None:
        request = setup.requests.add(setup.ana, AccessRequestType.DATA_CORRECTION, message="x")
        account = setup.service.approve(request.id, setup.leader)
        assert account.member_access is False
        assert account.requests[0].status is AccessRequestStatus.APPROVED

    def test_already_decided_is_a_conflict(self, setup: Setup) -> None:
        request = setup.requests.add(
            setup.ana, AccessRequestType.ACCESS, status=AccessRequestStatus.DENIED
        )
        with pytest.raises(AccessRequestNotPendingError):
            setup.service.approve(request.id, setup.leader)
        assert setup.push.sent == []

    def test_unknown_request(self, setup: Setup) -> None:
        with pytest.raises(AccessRequestNotFoundError):
            setup.service.approve(999, setup.leader)


class TestDeny:
    def test_reason_is_trimmed_and_pushed(self, setup: Setup) -> None:
        request = setup.requests.add(setup.ana, AccessRequestType.ACCESS)
        account = setup.service.deny(request.id, setup.leader, "  Procure o pastor.  ")
        assert account.member_access is False
        assert account.requests[0].denial_reason == "Procure o pastor."
        _, message = setup.push.sent[0]
        assert message.as_data()["reason"] == "Procure o pastor."

    def test_blank_reason_is_absent(self, setup: Setup) -> None:
        request = setup.requests.add(setup.ana, AccessRequestType.ACCESS)
        account = setup.service.deny(request.id, setup.leader, "   ")
        assert account.requests[0].denial_reason is None
        assert "reason" not in setup.push.sent[0][1].as_data()


class TestGrant:
    def test_sets_the_flag_records_the_leader_and_notifies(self, setup: Setup) -> None:
        account = setup.service.grant_access(setup.ana, setup.leader)
        assert account.member_access is True
        assert account.access_granted_by is not None
        assert account.access_granted_by.id == setup.leader
        assert account.access_granted_at == NOW
        recipients, message = setup.push.sent[0]
        assert recipients == {setup.ana}
        assert message.as_data() == {"type": "access_request_approved", "request_type": "access"}

    def test_approves_the_pending_access_request(self, setup: Setup) -> None:
        request = setup.requests.add(setup.ana, AccessRequestType.ACCESS)
        account = setup.service.grant_access(setup.ana, setup.leader)
        assert account.pending_requests == []
        assert account.requests[0].status is AccessRequestStatus.APPROVED
        assert setup.push.sent[0][1].request_id == request.id

    def test_leaves_a_pending_correction_alone(self, setup: Setup) -> None:
        setup.requests.add(setup.ana, AccessRequestType.DATA_CORRECTION, message="x")
        account = setup.service.grant_access(setup.ana, setup.leader)
        assert [r.type for r in account.pending_requests] == [AccessRequestType.DATA_CORRECTION]
        assert setup.push.sent[0][1].request_id is None

    def test_flagged_account_is_unchanged_without_push(self, setup: Setup) -> None:
        flagged = setup.account(member_access=True)
        account = setup.service.grant_access(flagged, setup.leader)
        assert account.member_access is True
        assert account.access_granted_by is None
        assert setup.push.sent == []

    def test_unknown_account(self, setup: Setup) -> None:
        with pytest.raises(ManagedAccountNotFoundError):
            setup.service.grant_access(uuid4(), setup.leader)


class TestManage:
    def test_revoke_clears_the_flag_and_grant_without_push(self, setup: Setup) -> None:
        setup.service.grant_access(setup.ana, setup.leader)
        setup.push.sent.clear()
        account = setup.service.revoke_access(setup.ana)
        assert account.member_access is False
        assert account.access_granted_by is None
        assert account.access_granted_at is None
        assert setup.push.sent == []

    def test_update_applies_the_patch_without_push(self, setup: Setup) -> None:
        account = setup.service.update_account(
            setup.ana, ManagedAccountPatchDTO(access_requests_blocked=True)
        )
        assert account.access_requests_blocked is True
        assert setup.push.sent == []

    def test_unknown_account(self, setup: Setup) -> None:
        with pytest.raises(ManagedAccountNotFoundError):
            setup.service.revoke_access(uuid4())
        with pytest.raises(ManagedAccountNotFoundError):
            setup.service.get_account(uuid4())
