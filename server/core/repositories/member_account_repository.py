from collections.abc import Collection
from uuid import UUID

from django.contrib.auth import get_user_model
from django.db.models import Q

from core.domain.access import MEMBER_ACCESS_ROLES

# Lookup strings, never imports: core must not import the members or accounts features. The path
# is User -> Profile (accounts) -> Member (members).
_MEMBER_ID_LOOKUP = "profile__member_id"
_MEMBER_ACCESS_ROLE_NAMES = sorted(role.value for role in MEMBER_ACCESS_ROLES)


class MemberAccountRepositoryImpl:
    """The app account linked to each roll member, when it may read member content
    (specs/024-schedule-reminders R-03).

    Member access is the profile flag or an Admin/Liderança group, the same rule as
    ``core.domain.access.has_member_access``. Inactive accounts are left out: they cannot sign in.
    """

    def user_ids_by_member(self, member_ids: Collection[int]) -> dict[int, UUID]:
        """One query. ``Profile.member`` is one-to-one, so each member has at most one account.

        >>> MemberAccountRepositoryImpl().user_ids_by_member({7, 9})
        {7: UUID('...')}
        """
        if not member_ids:
            return {}
        has_access = Q(profile__member_access=True) | Q(groups__name__in=_MEMBER_ACCESS_ROLE_NAMES)
        rows = (
            get_user_model()
            .objects.filter(is_active=True, **{f"{_MEMBER_ID_LOOKUP}__in": list(member_ids)})
            .filter(has_access)
            .values_list(_MEMBER_ID_LOOKUP, "pk")
            .distinct()
        )
        return {member_id: user_id for member_id, user_id in rows}
