from collections import defaultdict
from uuid import UUID

from django.apps import apps
from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction
from django.db.models import Exists, F, Min, OuterRef, Q, QuerySet

from core.domain.access import MEMBER_ACCESS_ROLES
from core.domain.exceptions import RollMemberAlreadyLinkedError, RollMemberNotFoundError
from features.accounts.domain.access_requests import AccessRequestStatus
from features.accounts.dtos import (
    AccessGrantDTO,
    AccessRequestRecordDTO,
    AccountAccessFlagsDTO,
    LinkedMemberDTO,
    ManagedAccountDTO,
    ManagedAccountPatchDTO,
    PersonRefDTO,
)
from features.accounts.models.access_request import AccessRequest
from features.accounts.models.profile import Profile
from features.accounts.models.user import User
from features.accounts.repositories.access_request_repository import to_record

_PENDING = AccessRequestStatus.PENDING.value
_LEADERSHIP_GROUPS = [role.value for role in MEMBER_ACCESS_ROLES]


def _accounts() -> QuerySet[User]:
    """Active accounts with what "Perfis" shows, in one query: the profile, its roll link and its
    granting leader joined, the leadership role and the oldest pending request annotated."""
    leadership = Group.objects.filter(user=OuterRef("pk"), name__in=_LEADERSHIP_GROUPS)
    oldest_pending = Min("access_requests__created_at", filter=Q(access_requests__status=_PENDING))
    return (
        User.objects.filter(is_active=True)
        .select_related("profile__member", "profile__access_granted_by__profile")
        .annotate(access_via_role=Exists(leadership), oldest_pending=oldest_pending)
    )


class ManagedAccountRepositoryImpl:
    """App accounts for "Perfis" (specs/022-access-requests). The roll is reached by string
    (``apps.get_model``, ``profile__member``) so accounts never imports the members feature.

    >>> ManagedAccountRepositoryImpl().list_accounts(pending_only=True)
    [ManagedAccountDTO(...)]
    """

    def access_flags(self, user_id: UUID) -> AccountAccessFlagsDTO:
        profile = Profile.objects.filter(user_id=user_id).first()
        return AccountAccessFlagsDTO(
            member_access=bool(profile and profile.member_access),
            access_requests_blocked=bool(profile and profile.access_requests_blocked),
        )

    def list_accounts(self, pending_only: bool) -> list[ManagedAccountDTO]:
        accounts = _accounts()
        if pending_only:
            # Q and F, not strings: the stubs only know model fields, not annotations.
            pending = Q(oldest_pending__isnull=False)
            accounts = accounts.filter(pending).order_by(F("oldest_pending").asc())
        else:
            accounts = accounts.order_by("profile__name", "username")
        return self._with_pending(list(accounts))

    def get_account(self, user_id: UUID) -> ManagedAccountDTO | None:
        found = _accounts().filter(pk=user_id).first()
        return self._with_pending([found])[0] if found else None

    def grant_member_access(self, user_id: UUID, grant: AccessGrantDTO) -> None:
        granted = {
            "member_access": True,
            "access_granted_by_id": grant.granted_by,
            "access_granted_at": grant.granted_at,
        }
        Profile.objects.update_or_create(user_id=user_id, defaults=granted)

    def revoke_member_access(self, user_id: UUID) -> None:
        revoked = {"member_access": False, "access_granted_by": None, "access_granted_at": None}
        Profile.objects.update_or_create(user_id=user_id, defaults=revoked)

    def update(self, user_id: UUID, patch: ManagedAccountPatchDTO) -> None:
        fields: dict[str, object] = {}
        if "access_requests_blocked" in patch.model_fields_set:
            fields["access_requests_blocked"] = bool(patch.access_requests_blocked)
        if "member_id" in patch.model_fields_set:
            fields["member_id"] = self._existing_member_id(patch.member_id)
        if not fields:
            return
        try:
            self._save_profile_fields(user_id, fields)
        except IntegrityError as exc:
            # The only unique column written here is the one-to-one roll link.
            raise RollMemberAlreadyLinkedError(patch.member_id or 0) from exc

    def _existing_member_id(self, member_id: int | None) -> int | None:
        member_model = apps.get_model("members", "Member")
        if member_id is not None and not member_model.objects.filter(pk=member_id).exists():
            raise RollMemberNotFoundError(member_id)
        return member_id

    def _save_profile_fields(self, user_id: UUID, fields: dict[str, object]) -> None:
        # Savepoint: the one-to-one's IntegrityError must not poison an outer transaction.
        with transaction.atomic():
            Profile.objects.update_or_create(user_id=user_id, defaults=fields)

    def _with_pending(self, accounts: list[User]) -> list[ManagedAccountDTO]:
        # Every pending request of the page in one query, never one per account.
        pending: dict[UUID, list[AccessRequestRecordDTO]] = defaultdict(list)
        rows = AccessRequest.objects.filter(
            user_id__in=[account.pk for account in accounts], status=_PENDING
        ).order_by("created_at", "id")
        for row in rows:
            pending[row.user_id].append(to_record(row))
        return [_to_account(account, pending[account.pk]) for account in accounts]


def _to_account(account: User, pending: list[AccessRequestRecordDTO]) -> ManagedAccountDTO:
    profile: Profile | None = getattr(account, "profile", None)
    return ManagedAccountDTO(
        id=account.pk,
        name=(profile.name if profile else "") or "",
        username=account.username,
        photo_path=profile.photo.url if profile and profile.photo else None,
        member_access=bool(profile and profile.member_access),
        access_via_role=bool(getattr(account, "access_via_role", False)),
        access_requests_blocked=bool(profile and profile.access_requests_blocked),
        access_granted_by=_granter(profile),
        access_granted_at=profile.access_granted_at if profile else None,
        member=_linked_member(profile),
        date_joined=account.date_joined,
        pending_requests=pending,
    )


def _granter(profile: Profile | None) -> PersonRefDTO | None:
    leader = profile.access_granted_by if profile else None
    if leader is None:
        return None
    # A leader without a profile row has no name to show, not an error.
    leader_profile = getattr(leader, "profile", None)
    return PersonRefDTO(id=leader.pk, name=getattr(leader_profile, "name", "") or "")


def _linked_member(profile: Profile | None) -> LinkedMemberDTO | None:
    member = profile.member if profile else None
    if member is None:
        return None
    return LinkedMemberDTO(id=member.pk, name=member.name)
