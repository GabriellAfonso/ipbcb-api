"""Named fakes for the access-request services (specs/022-access-requests). Their own module so
``fakes.py`` stays focused on sign-in and account deletion."""

from collections.abc import Collection
from datetime import datetime
from uuid import UUID

from core.application.dtos.access_dtos import AccessGrantsDTO
from core.application.dtos.push_dtos import PushMessage, PushOutcome
from core.domain.access import Level, Role, Scope
from core.domain.exceptions import (
    AccessRequestNotFoundError,
    AccessRequestNotPendingError,
    AccessRequestPendingError,
)
from features.accounts.domain.access_requests import AccessRequestStatus, AccessRequestType
from features.accounts.dtos import (
    AccessDecisionDTO,
    AccessGrantDTO,
    AccessRequestCreateDTO,
    AccessRequestRecordDTO,
    AccountAccessFlagsDTO,
    ManagedAccountDTO,
    ManagedAccountPatchDTO,
    PersonRefDTO,
)


class FixedClock:
    """>>> FixedClock(moment).now() == moment
    True
    """

    def __init__(self, moment: datetime) -> None:
        self.moment = moment

    def now(self) -> datetime:
        return self.moment


class FakeAccessRequestRepository:
    """In-memory requests; ``created_at`` comes from the shared clock, like ``auto_now_add``."""

    def __init__(self, clock: FixedClock) -> None:
        self.clock = clock
        self.rows: dict[int, AccessRequestRecordDTO] = {}

    def add(
        self, user_id: UUID, kind: AccessRequestType, **fields: object
    ) -> AccessRequestRecordDTO:
        """Seed a row directly (any status, any date)."""
        values: dict[str, object] = {
            "id": len(self.rows) + 1,
            "user_id": user_id,
            "type": kind,
            "message": None,
            "status": AccessRequestStatus.PENDING,
            "created_at": self.clock.now(),
            "decided_by": None,
            "decided_at": None,
            "denial_reason": None,
        }
        values.update(fields)
        record = AccessRequestRecordDTO.model_validate(values)
        self.rows[record.id] = record
        return record

    def latest_created_at(self, user_id: UUID) -> datetime | None:
        dates = [row.created_at for row in self.rows.values() if row.user_id == user_id]
        return max(dates, default=None)

    def pending_types(self, user_id: UUID) -> set[AccessRequestType]:
        return {row.type for row in self._pending() if row.user_id == user_id}

    def create(self, user_id: UUID, request: AccessRequestCreateDTO) -> AccessRequestRecordDTO:
        if request.type in self.pending_types(user_id):
            raise AccessRequestPendingError(request.type.value)
        return self.add(user_id, request.type, message=request.message)

    def get(self, request_id: int) -> AccessRequestRecordDTO | None:
        return self.rows.get(request_id)

    def pending_id(self, user_id: UUID, kind: AccessRequestType) -> int | None:
        ids = [row.id for row in self._pending() if row.user_id == user_id and row.type is kind]
        return ids[0] if ids else None

    def decide(self, request_id: int, decision: AccessDecisionDTO) -> AccessRequestRecordDTO:
        row = self.rows.get(request_id)
        if row is None:
            raise AccessRequestNotFoundError(request_id)
        if row.status is not AccessRequestStatus.PENDING:
            raise AccessRequestNotPendingError(request_id, row.status.value)
        decided = row.model_copy(
            update={
                "status": decision.status,
                "decided_by": PersonRefDTO(id=decision.decided_by, name="Líder"),
                "decided_at": decision.decided_at,
                "denial_reason": decision.denial_reason,
            }
        )
        self.rows[request_id] = decided
        return decided

    def list_for_user(self, user_id: UUID) -> list[AccessRequestRecordDTO]:
        mine = [row for row in self.rows.values() if row.user_id == user_id]
        return sorted(mine, key=lambda row: row.id, reverse=True)

    def _pending(self) -> list[AccessRequestRecordDTO]:
        return [row for row in self.rows.values() if row.status is AccessRequestStatus.PENDING]


class FakeManagedAccountRepository:
    """In-memory accounts keyed by id; each account is a ``ManagedAccountDTO``."""

    def __init__(self, requests: FakeAccessRequestRepository) -> None:
        self.requests = requests
        self.accounts: dict[UUID, ManagedAccountDTO] = {}
        self.patches: list[tuple[UUID, ManagedAccountPatchDTO]] = []

    def access_flags(self, user_id: UUID) -> AccountAccessFlagsDTO:
        account = self.accounts.get(user_id)
        return AccountAccessFlagsDTO(
            member_access=bool(account and account.member_access),
            access_requests_blocked=bool(account and account.access_requests_blocked),
        )

    def list_accounts(self, pending_only: bool) -> list[ManagedAccountDTO]:
        accounts = [self._with_pending(account) for account in self.accounts.values()]
        return [a for a in accounts if a.pending_requests] if pending_only else accounts

    def get_account(self, user_id: UUID) -> ManagedAccountDTO | None:
        account = self.accounts.get(user_id)
        return self._with_pending(account) if account else None

    def grant_member_access(self, user_id: UUID, grant: AccessGrantDTO) -> None:
        granted = {
            "member_access": True,
            "access_granted_by": PersonRefDTO(id=grant.granted_by, name="Líder"),
            "access_granted_at": grant.granted_at,
        }
        self.accounts[user_id] = self.accounts[user_id].model_copy(update=granted)

    def revoke_member_access(self, user_id: UUID) -> None:
        revoked = {"member_access": False, "access_granted_by": None, "access_granted_at": None}
        self.accounts[user_id] = self.accounts[user_id].model_copy(update=revoked)

    def update(self, user_id: UUID, patch: ManagedAccountPatchDTO) -> None:
        self.patches.append((user_id, patch))
        if "access_requests_blocked" in patch.model_fields_set:
            blocked = bool(patch.access_requests_blocked)
            self.accounts[user_id] = self.accounts[user_id].model_copy(
                update={"access_requests_blocked": blocked}
            )

    def _with_pending(self, account: ManagedAccountDTO) -> ManagedAccountDTO:
        pending = [
            row
            for row in self.requests.list_for_user(account.id)
            if row.status is AccessRequestStatus.PENDING
        ]
        return account.model_copy(update={"pending_requests": pending})


class FakeRoleDirectory:
    """Fixed roles per user, and a fixed set of ``profiles`` managers."""

    def __init__(
        self, roles: dict[UUID, list[Role]] | None = None, managers: set[UUID] | None = None
    ) -> None:
        self.roles = roles or {}
        self.managers = managers or set()
        self.asked_levels: list[tuple[Scope, Level]] = []

    def grants_for(self, user_id: UUID) -> AccessGrantsDTO:
        return AccessGrantsDTO(roles=self.roles.get(user_id, []), levels={})

    def user_ids_with_level(self, scope: Scope, level: Level) -> set[UUID]:
        self.asked_levels.append((scope, level))
        return set(self.managers)


class RecordingPushNotifier:
    """Records every notification instead of sending it."""

    def __init__(self) -> None:
        self.sent: list[tuple[set[UUID], PushMessage]] = []

    def notify(self, user_ids: Collection[UUID], message: PushMessage) -> PushOutcome:
        self.sent.append((set(user_ids), message))
        return PushOutcome(recipients=len(user_ids))
