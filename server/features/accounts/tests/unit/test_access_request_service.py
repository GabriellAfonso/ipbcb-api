"""AccessRequestService on fakes (specs/022-access-requests US1, US5, FR-004 to FR-010)."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from core.domain.access import Level, Role, Scope
from core.domain.exceptions import (
    AccessRequestMessageRequiredError,
    AccessRequestPendingError,
    AccessRequestRateLimitedError,
    AccessRequestsBlockedError,
    MemberAccessAlreadyGrantedError,
)
from core.domain.push import PushMessageType
from features.accounts.domain.access_requests import (
    AccessRequestStatus,
    AccessRequestType,
    AccessStatus,
)
from features.accounts.dtos import AccessRequestCreateDTO, ManagedAccountDTO
from features.accounts.services.access_request_service import AccessRequestService
from features.accounts.tests.access_fakes import (
    FakeAccessRequestRepository,
    FakeManagedAccountRepository,
    FakeRoleDirectory,
    FixedClock,
    RecordingPushNotifier,
)

NOW = datetime(2026, 10, 21, 12, tzinfo=UTC)
ACCESS = AccessRequestCreateDTO(type=AccessRequestType.ACCESS)
CORRECTION = AccessRequestCreateDTO(
    type=AccessRequestType.DATA_CORRECTION, message="Meu batismo foi em 2001."
)


class Setup:
    def __init__(self) -> None:
        self.clock = FixedClock(NOW)
        self.requests = FakeAccessRequestRepository(self.clock)
        self.accounts = FakeManagedAccountRepository(self.requests)
        self.leader = uuid4()
        self.roles = FakeRoleDirectory(managers={self.leader})
        self.push = RecordingPushNotifier()
        self.service = AccessRequestService(
            self.requests, self.accounts, self.roles, self.push, self.clock
        )
        self.ana = self.account()

    def account(self, member_access: bool = False, blocked: bool = False) -> UUID:
        user_id = uuid4()
        self.accounts.accounts[user_id] = ManagedAccountDTO(
            id=user_id,
            name="Ana",
            username=f"u{user_id.hex[:6]}",
            photo_path=None,
            member_access=member_access,
            access_via_role=False,
            access_requests_blocked=blocked,
            member=None,
            date_joined=NOW,
        )
        return user_id


@pytest.fixture
def setup() -> Setup:
    return Setup()


class TestCreateRequest:
    def test_access_request_is_stored_pending(self, setup: Setup) -> None:
        record = setup.service.create_request(setup.ana, ACCESS)
        assert record.status is AccessRequestStatus.PENDING
        assert record.user_id == setup.ana

    def test_leaders_are_notified_without_the_requester(self, setup: Setup) -> None:
        setup.roles.managers.add(setup.ana)
        record = setup.service.create_request(setup.ana, ACCESS)
        recipients, message = setup.push.sent[0]
        assert recipients == {setup.leader}
        assert message.type is PushMessageType.ACCESS_REQUEST_CREATED
        assert message.as_data() == {
            "type": "access_request_created",
            "request_id": str(record.id),
            "request_type": "access",
        }
        assert setup.roles.asked_levels == [(Scope.PROFILES, Level.MANAGE)]

    def test_correction_needs_a_message(self, setup: Setup) -> None:
        empty = AccessRequestCreateDTO(type=AccessRequestType.DATA_CORRECTION, message="  ")
        with pytest.raises(AccessRequestMessageRequiredError):
            setup.service.create_request(setup.ana, empty)

    def test_correction_with_message_is_stored(self, setup: Setup) -> None:
        record = setup.service.create_request(setup.ana, CORRECTION)
        assert record.message == "Meu batismo foi em 2001."

    def test_blocked_account_is_refused_first(self, setup: Setup) -> None:
        blocked = setup.account(member_access=True, blocked=True)
        with pytest.raises(AccessRequestsBlockedError) as error:
            setup.service.create_request(blocked, ACCESS)
        assert str(error.value) == "Pedidos de acesso indisponíveis. Fale com a liderança."
        assert setup.push.sent == []

    def test_flag_holder_cannot_ask_for_access(self, setup: Setup) -> None:
        with pytest.raises(MemberAccessAlreadyGrantedError):
            setup.service.create_request(setup.account(member_access=True), ACCESS)

    def test_leader_without_flag_cannot_ask_for_access(self, setup: Setup) -> None:
        setup.roles.roles[setup.ana] = [Role.LEADER]
        with pytest.raises(MemberAccessAlreadyGrantedError):
            setup.service.create_request(setup.ana, ACCESS)

    def test_flag_holder_may_ask_for_a_correction(self, setup: Setup) -> None:
        record = setup.service.create_request(setup.account(member_access=True), CORRECTION)
        assert record.type is AccessRequestType.DATA_CORRECTION

    def test_pending_of_same_type_wins_over_the_day_limit(self, setup: Setup) -> None:
        setup.requests.add(setup.ana, AccessRequestType.ACCESS)
        with pytest.raises(AccessRequestPendingError):
            setup.service.create_request(setup.ana, ACCESS)

    def test_second_request_within_a_day_is_rate_limited(self, setup: Setup) -> None:
        setup.requests.add(
            setup.ana,
            AccessRequestType.ACCESS,
            status=AccessRequestStatus.DENIED,
            created_at=NOW - timedelta(hours=23),
        )
        with pytest.raises(AccessRequestRateLimitedError) as error:
            setup.service.create_request(setup.ana, CORRECTION)
        assert error.value.retry_after_seconds == 3600

    def test_request_after_a_day_is_accepted(self, setup: Setup) -> None:
        setup.requests.add(
            setup.ana,
            AccessRequestType.ACCESS,
            status=AccessRequestStatus.DENIED,
            created_at=NOW - timedelta(hours=24),
        )
        assert setup.service.create_request(setup.ana, ACCESS).status is AccessRequestStatus.PENDING


class TestAccessState:
    def test_nothing(self, setup: Setup) -> None:
        state = setup.service.access_state(setup.ana, flag=False, roles=[])
        assert state.member_access is False
        assert state.access_status is AccessStatus.NONE
        assert state.data_correction_pending is False

    def test_pending_access_and_correction(self, setup: Setup) -> None:
        setup.requests.add(setup.ana, AccessRequestType.ACCESS)
        setup.requests.add(setup.ana, AccessRequestType.DATA_CORRECTION)
        state = setup.service.access_state(setup.ana, flag=False, roles=[Role.MEDIA])
        assert state.access_status is AccessStatus.PENDING
        assert state.data_correction_pending is True

    @pytest.mark.parametrize(("flag", "roles"), [(True, []), (False, [Role.ADMIN])])
    def test_granted_by_flag_or_role(self, setup: Setup, flag: bool, roles: list[Role]) -> None:
        setup.requests.add(setup.ana, AccessRequestType.ACCESS)
        state = setup.service.access_state(setup.ana, flag=flag, roles=roles)
        assert state.member_access is True
        assert state.access_status is AccessStatus.GRANTED
