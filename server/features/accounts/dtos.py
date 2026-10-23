"""Data carried between the layers of access requests and "Perfis"
(specs/022-access-requests/data-model.md). Auth DTOs stay in ``core/application/dtos``."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, field_validator

from core.application.dtos.strict_base import StrictBaseModel
from features.accounts.domain.access_requests import (
    AccessRequestStatus,
    AccessRequestType,
    AccessStatus,
    clean_text,
)


class AccessRequestCreateDTO(StrictBaseModel):
    """A new request. ``message`` is trimmed; blank becomes None.

    >>> AccessRequestCreateDTO(type=AccessRequestType.ACCESS, message="  ").message
    """

    type: AccessRequestType
    message: str | None = None

    _message = field_validator("message")(clean_text)


class PersonRefDTO(BaseModel):
    """An account as the panel names it. ``name`` is the profile name, maybe ""."""

    id: UUID
    name: str


class AccessRequestRecordDTO(BaseModel):
    """A request as stored."""

    id: int
    user_id: UUID
    type: AccessRequestType
    message: str | None
    status: AccessRequestStatus
    created_at: datetime
    decided_by: PersonRefDTO | None
    decided_at: datetime | None
    denial_reason: str | None


class LinkedMemberDTO(BaseModel):
    """The roll record an account is linked to: id and name only, never other roll fields."""

    id: int
    name: str


class ManagedAccountDTO(BaseModel):
    """An app account as "Perfis" shows it. ``member_access`` is the stored flag;
    ``access_via_role`` says a leadership role grants access anyway; ``access_granted_by`` /
    ``access_granted_at`` record who set the flag and when (spec FR-017b). No e-mail (FR-019)."""

    id: UUID
    name: str
    username: str
    photo_path: str | None
    member_access: bool
    access_via_role: bool
    access_requests_blocked: bool
    access_granted_by: PersonRefDTO | None = None
    access_granted_at: datetime | None = None
    member: LinkedMemberDTO | None
    date_joined: datetime
    pending_requests: list[AccessRequestRecordDTO] = []


class ManagedAccountDetailDTO(ManagedAccountDTO):
    """The account plus its whole request history, newest first."""

    requests: list[AccessRequestRecordDTO] = []


class ManagedAccountPatchDTO(StrictBaseModel):
    """Leader edits of an account. Only ``model_fields_set`` is applied: an absent field is left
    alone; ``member_id`` sent as None removes the link.

    >>> ManagedAccountPatchDTO(member_id=None).model_fields_set
    {'member_id'}
    """

    access_requests_blocked: bool | None = None
    member_id: int | None = None


class MemberAccessStateDTO(StrictBaseModel):
    """What ``/me`` says about member access (spec FR-004).

    >>> MemberAccessStateDTO(member_access=False, access_status=AccessStatus.PENDING,
    ...                      data_correction_pending=False).access_status
    <AccessStatus.PENDING: 'pending'>
    """

    member_access: bool
    access_status: AccessStatus
    data_correction_pending: bool


class AccessDecisionDTO(StrictBaseModel):
    """A leader's decision on a pending request.

    >>> AccessDecisionDTO(status=AccessRequestStatus.DENIED, decided_by=leader_id,
    ...                   decided_at=now, denial_reason=None).status
    <AccessRequestStatus.DENIED: 'denied'>
    """

    status: AccessRequestStatus
    decided_by: UUID
    decided_at: datetime
    denial_reason: str | None = None


class AccessGrantDTO(StrictBaseModel):
    """A leader setting an account's member-access flag (spec FR-017b).

    >>> AccessGrantDTO(granted_by=leader_id, granted_at=now).granted_by == leader_id
    True
    """

    granted_by: UUID
    granted_at: datetime


class AccountAccessFlagsDTO(StrictBaseModel):
    """The profile's stored member-access and block flags."""

    member_access: bool
    access_requests_blocked: bool
