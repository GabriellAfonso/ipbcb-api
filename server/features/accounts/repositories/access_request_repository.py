from datetime import datetime
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import QuerySet

from core.domain.exceptions import (
    AccessRequestNotFoundError,
    AccessRequestNotPendingError,
    AccessRequestPendingError,
)
from features.accounts.domain.access_requests import AccessRequestStatus, AccessRequestType
from features.accounts.dtos import (
    AccessDecisionDTO,
    AccessRequestCreateDTO,
    AccessRequestRecordDTO,
    PersonRefDTO,
)
from features.accounts.models.access_request import AccessRequest

_PENDING = AccessRequestStatus.PENDING.value


def _with_decider() -> QuerySet[AccessRequest]:
    # The decider's profile name is shown to the panel; joined so a history is one query.
    return AccessRequest.objects.select_related("decided_by__profile")


class AccessRequestRepositoryImpl:
    """ORM persistence of access requests (specs/022-access-requests/data-model.md).

    >>> AccessRequestRepositoryImpl().pending_types(ana.pk)
    {<AccessRequestType.ACCESS: 'access'>}
    """

    def latest_created_at(self, user_id: UUID) -> datetime | None:
        latest = AccessRequest.objects.filter(user_id=user_id).order_by("-created_at").first()
        return latest.created_at if latest else None

    def pending_types(self, user_id: UUID) -> set[AccessRequestType]:
        kinds = AccessRequest.objects.filter(user_id=user_id, status=_PENDING).values_list(
            "type", flat=True
        )
        return {AccessRequestType(kind) for kind in kinds}

    def create(self, user_id: UUID, request: AccessRequestCreateDTO) -> AccessRequestRecordDTO:
        try:
            # Savepoint: the IntegrityError must not poison an outer transaction.
            with transaction.atomic():
                created = AccessRequest.objects.create(
                    user_id=user_id, type=request.type.value, message=request.message
                )
        except IntegrityError as exc:
            raise AccessRequestPendingError(request.type.value) from exc
        return to_record(created)

    def get(self, request_id: int) -> AccessRequestRecordDTO | None:
        found = _with_decider().filter(pk=request_id).first()
        return to_record(found) if found else None

    def decide(self, request_id: int, decision: AccessDecisionDTO) -> AccessRequestRecordDTO:
        # Conditional update: two leaders deciding at once cannot both win.
        updated = AccessRequest.objects.filter(pk=request_id, status=_PENDING).update(
            status=decision.status.value,
            decided_by_id=decision.decided_by,
            decided_at=decision.decided_at,
            denial_reason=decision.denial_reason,
        )
        record = self.get(request_id)
        if record is None:
            raise AccessRequestNotFoundError(request_id)
        if not updated:
            raise AccessRequestNotPendingError(request_id, record.status.value)
        return record

    def list_for_user(self, user_id: UUID) -> list[AccessRequestRecordDTO]:
        return [to_record(found) for found in _with_decider().filter(user_id=user_id)]


def to_record(request: AccessRequest) -> AccessRequestRecordDTO:
    """The DTO of a request row. Public: the managed-account repository maps pending requests
    it loads in bulk with it.

    >>> to_record(row).status
    <AccessRequestStatus.PENDING: 'pending'>
    """
    return AccessRequestRecordDTO(
        id=request.pk,
        user_id=request.user_id,
        type=AccessRequestType(request.type),
        message=request.message,
        status=AccessRequestStatus(request.status),
        created_at=request.created_at,
        decided_by=_person_of(request),
        decided_at=request.decided_at,
        denial_reason=request.denial_reason,
    )


def _person_of(request: AccessRequest) -> PersonRefDTO | None:
    decider = request.decided_by
    if decider is None:
        return None
    # A decider without a profile row has no name to show, not an error.
    profile = getattr(decider, "profile", None)
    return PersonRefDTO(id=decider.pk, name=getattr(profile, "name", "") or "")
