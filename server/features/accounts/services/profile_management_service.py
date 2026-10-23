from uuid import UUID

from django.db import transaction

from core.application.dtos.push_dtos import PushMessage
from core.domain.exceptions import (
    AccessRequestNotPendingError,
    ManagedAccountNotFoundError,
    ProfileStatusFilterError,
)
from core.domain.push import PushMessageType
from core.time.clock import Clock
from features.accounts.domain.access_requests import (
    AccessRequestStatus,
    AccessRequestType,
    ProfileListFilter,
    clean_text,
)
from features.accounts.dtos import (
    AccessDecisionDTO,
    AccessGrantDTO,
    AccessRequestRecordDTO,
    ManagedAccountDTO,
    ManagedAccountDetailDTO,
    ManagedAccountPatchDTO,
)
from features.accounts.repositories.interfaces import (
    AccessRequestRepository,
    ManagedAccountRepository,
)
from features.accounts.services.access_request_service import PushNotifier

_PUSH_BY_STATUS = {
    AccessRequestStatus.APPROVED: PushMessageType.ACCESS_REQUEST_APPROVED,
    AccessRequestStatus.DENIED: PushMessageType.ACCESS_REQUEST_DENIED,
}


def parse_list_filter(raw: str | None) -> ProfileListFilter:
    """The ``status`` query value; absent means "all" (Todos).

    >>> parse_list_filter("pending")
    <ProfileListFilter.PENDING: 'pending'>
    """
    if raw is None:
        return ProfileListFilter.ALL
    try:
        return ProfileListFilter(raw)
    except ValueError as exc:
        raise ProfileStatusFilterError(raw, [item.value for item in ProfileListFilter]) from exc


class ProfileManagementService:
    """ "Perfis": leaders see app accounts, decide their requests, grant and revoke access, block
    requests and link accounts to the roll (specs/022-access-requests US2, US3). The scope check is the
    view's; nothing here knows roles.
    """

    def __init__(
        self,
        request_repository: AccessRequestRepository,
        account_repository: ManagedAccountRepository,
        push_notifier: PushNotifier,
        clock: Clock,
    ) -> None:
        self._requests = request_repository
        self._accounts = account_repository
        self._push = push_notifier
        self._clock = clock

    def list_accounts(self, status_raw: str | None) -> list[ManagedAccountDTO]:
        """>>> service.list_accounts("pending")[0].pending_requests[0].type
        <AccessRequestType.ACCESS: 'access'>
        """
        pending_only = parse_list_filter(status_raw) is ProfileListFilter.PENDING
        return self._accounts.list_accounts(pending_only=pending_only)

    def get_account(self, user_id: UUID) -> ManagedAccountDetailDTO:
        """The account with its whole request history.

        >>> service.get_account(ana.pk).requests[0].status
        <AccessRequestStatus.DENIED: 'denied'>
        """
        account = self._accounts.get_account(user_id)
        if account is None:
            raise ManagedAccountNotFoundError(user_id)
        history = self._requests.list_for_user(user_id)
        return ManagedAccountDetailDTO(**account.model_dump(), requests=history)

    def approve(self, request_id: int, leader_id: UUID) -> ManagedAccountDetailDTO:
        """Approve a pending request: an ``access`` one sets the flag (recording the grant unless
        the flag was already set, FR-017b), a ``data_correction`` one is only closed. The
        requester is notified after the commit.

        >>> service.approve(41, leader.pk).member_access
        True
        """
        decision = self._decision(AccessRequestStatus.APPROVED, leader_id, None)
        with transaction.atomic():
            record = self._requests.decide(request_id, decision)
            if record.type is AccessRequestType.ACCESS:
                self._grant_unless_flagged(record.user_id, leader_id)
        return self._notified(record)

    def deny(self, request_id: int, leader_id: UUID, reason: str | None) -> ManagedAccountDetailDTO:
        """Deny a pending request; the account is unchanged.

        >>> service.deny(41, leader.pk, "Procure o pastor.").requests[0].denial_reason
        'Procure o pastor.'
        """
        decision = self._decision(AccessRequestStatus.DENIED, leader_id, clean_text(reason))
        record = self._requests.decide(request_id, decision)
        return self._notified(record)

    def grant_access(self, user_id: UUID, leader_id: UUID) -> ManagedAccountDetailDTO:
        """Set the stored flag without a request (spec FR-017a). A pending ``access`` request is
        approved by the same leader; the account gets the approval push after the commit. An
        account already flagged is left alone, with no push.

        >>> service.grant_access(ana.pk, leader.pk).access_granted_by.id == leader.pk
        True
        """
        account = self.get_account(user_id)
        if account.member_access:
            return account
        with transaction.atomic():
            approved = self._approve_pending_access(user_id, leader_id)
            self._accounts.grant_member_access(user_id, self._grant(leader_id))
        message = PushMessage(
            type=PushMessageType.ACCESS_REQUEST_APPROVED,
            request_id=approved.id if approved else None,
            request_type=AccessRequestType.ACCESS.value,
        )
        self._push.notify({user_id}, message)
        return self.get_account(user_id)

    def revoke_access(self, user_id: UUID) -> ManagedAccountDetailDTO:
        """Clear the stored flag and its grant record. No push (spec FR-017).

        >>> service.revoke_access(ana.pk).member_access
        False
        """
        self.get_account(user_id)
        self._accounts.revoke_member_access(user_id)
        return self.get_account(user_id)

    def update_account(
        self, user_id: UUID, patch: ManagedAccountPatchDTO
    ) -> ManagedAccountDetailDTO:
        """Block/unblock requests and link/unlink the roll member. No push.

        >>> service.update_account(ana.pk, ManagedAccountPatchDTO(member_id=12)).member.id
        12
        """
        self.get_account(user_id)
        self._accounts.update(user_id, patch)
        return self.get_account(user_id)

    def _grant(self, leader_id: UUID) -> AccessGrantDTO:
        return AccessGrantDTO(granted_by=leader_id, granted_at=self._clock.now())

    def _grant_unless_flagged(self, user_id: UUID, leader_id: UUID) -> None:
        # Approving for an account flagged another way keeps the earlier grant record.
        if not self._accounts.access_flags(user_id).member_access:
            self._accounts.grant_member_access(user_id, self._grant(leader_id))

    def _approve_pending_access(
        self, user_id: UUID, leader_id: UUID
    ) -> AccessRequestRecordDTO | None:
        request_id = self._requests.pending_id(user_id, AccessRequestType.ACCESS)
        if request_id is None:
            return None
        decision = self._decision(AccessRequestStatus.APPROVED, leader_id, None)
        try:
            return self._requests.decide(request_id, decision)
        except AccessRequestNotPendingError:
            # Another leader decided it a moment ago: the grant stands, their decision too.
            return None

    def _decision(
        self, status: AccessRequestStatus, leader_id: UUID, reason: str | None
    ) -> AccessDecisionDTO:
        return AccessDecisionDTO(
            status=status, decided_by=leader_id, decided_at=self._clock.now(), denial_reason=reason
        )

    def _notified(self, record: AccessRequestRecordDTO) -> ManagedAccountDetailDTO:
        message = PushMessage(
            type=_PUSH_BY_STATUS[record.status],
            request_id=record.id,
            request_type=record.type.value,
            reason=record.denial_reason,
        )
        self._push.notify({record.user_id}, message)
        return self.get_account(record.user_id)
