from collections.abc import Collection
from typing import Protocol
from uuid import UUID

from core.application.dtos.access_dtos import AccessGrantsDTO
from core.application.dtos.push_dtos import PushMessage, PushOutcome
from core.domain.access import Level, Role, Scope, has_member_access
from core.domain.exceptions import (
    AccessRequestMessageRequiredError,
    AccessRequestPendingError,
    AccessRequestRateLimitedError,
    AccessRequestsBlockedError,
    MemberAccessAlreadyGrantedError,
)
from core.domain.push import PushMessageType
from core.time.clock import Clock
from features.accounts.domain.access_requests import (
    AccessRequestType,
    access_status,
    seconds_until_next_request,
)
from features.accounts.dtos import (
    AccessRequestCreateDTO,
    AccessRequestRecordDTO,
    MemberAccessStateDTO,
)
from features.accounts.repositories.interfaces import (
    AccessRequestRepository,
    ManagedAccountRepository,
)


class RoleDirectory(Protocol):
    """The part of ``core.application.access_service.AccessService`` this feature reads."""

    def grants_for(self, user_id: UUID) -> AccessGrantsDTO: ...

    def user_ids_with_level(self, scope: Scope, level: Level) -> set[UUID]: ...


class PushNotifier(Protocol):
    """The part of ``core.application.push_service.PushService`` this feature uses."""

    def notify(self, user_ids: Collection[UUID], message: PushMessage) -> PushOutcome: ...


class AccessRequestService:
    """An account asks the leadership for member access or a roll correction
    (specs/022-access-requests US1, US5), and ``/me`` learns where it stands (FR-004).
    """

    def __init__(
        self,
        request_repository: AccessRequestRepository,
        account_repository: ManagedAccountRepository,
        role_directory: RoleDirectory,
        push_notifier: PushNotifier,
        clock: Clock,
    ) -> None:
        self._requests = request_repository
        self._accounts = account_repository
        self._roles = role_directory
        self._push = push_notifier
        self._clock = clock

    def create_request(
        self, user_id: UUID, request: AccessRequestCreateDTO
    ) -> AccessRequestRecordDTO:
        """Store a pending request and tell the leaders. Refusals in the order of spec FR-010.

        >>> service.create_request(ana.pk, AccessRequestCreateDTO(type="access")).status
        <AccessRequestStatus.PENDING: 'pending'>
        """
        if request.type is AccessRequestType.DATA_CORRECTION and request.message is None:
            raise AccessRequestMessageRequiredError()
        self._refuse_if_not_allowed(user_id, request.type)
        record = self._requests.create(user_id, request)
        self._notify_leaders(record)
        return record

    def access_state(
        self, user_id: UUID, flag: bool, roles: Collection[Role]
    ) -> MemberAccessStateDTO:
        """>>> service.access_state(ana.pk, flag=False, roles=[]).access_status
        <AccessStatus.NONE: 'none'>
        """
        effective = has_member_access(flag, roles)
        pending = self._requests.pending_types(user_id)
        return MemberAccessStateDTO(
            member_access=effective,
            access_status=access_status(effective, AccessRequestType.ACCESS in pending),
            data_correction_pending=AccessRequestType.DATA_CORRECTION in pending,
        )

    def _refuse_if_not_allowed(self, user_id: UUID, request_type: AccessRequestType) -> None:
        flags = self._accounts.access_flags(user_id)
        if flags.access_requests_blocked:
            raise AccessRequestsBlockedError()
        if request_type is AccessRequestType.ACCESS and self._has_access(
            user_id, flags.member_access
        ):
            raise MemberAccessAlreadyGrantedError()
        if request_type in self._requests.pending_types(user_id):
            raise AccessRequestPendingError(request_type.value)
        latest = self._requests.latest_created_at(user_id)
        wait = seconds_until_next_request(latest, self._clock.now())
        if wait:
            raise AccessRequestRateLimitedError(retry_after_seconds=wait)

    def _has_access(self, user_id: UUID, flag: bool) -> bool:
        return flag or has_member_access(flag, self._roles.grants_for(user_id).roles)

    def _notify_leaders(self, record: AccessRequestRecordDTO) -> None:
        leaders = self._roles.user_ids_with_level(Scope.PROFILES, Level.MANAGE) - {record.user_id}
        message = PushMessage(
            type=PushMessageType.ACCESS_REQUEST_CREATED,
            request_id=record.id,
            request_type=record.type.value,
        )
        self._push.notify(leaders, message)
