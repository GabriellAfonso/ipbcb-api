from uuid import UUID

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db.models import Q

from core.application.dtos.access_dtos import RoleGrantRowsDTO
from core.domain.access import Level, Role, Scope, codenames_at_least

_ROLE_NAMES = [role.value for role in Role]


class RoleGrantRepositoryImpl:
    """Reads a user's panel roles straight from their groups.

    Not ``user.has_perm``: it answers ``True`` for any active superuser before asking a backend,
    and it also counts direct user permissions and every other group. Panel levels come from
    the three role groups alone (specs/012-feature-role-permissions FR-030, research R-10).

    Two queries: group names are needed even when the groups hold no permission (Admin holds
    none), and filtering the permission side by content type in one join would drop them.
    """

    def role_grants(self, user_id: UUID) -> RoleGrantRowsDTO:
        """>>> RoleGrantRepositoryImpl().role_grants(leader.pk).role_names
        ['leader']
        """
        role_names = Group.objects.filter(user__pk=user_id, name__in=_ROLE_NAMES).values_list(
            "name", flat=True
        )
        codenames = (
            Permission.objects.filter(
                group__user__pk=user_id,
                group__name__in=_ROLE_NAMES,
                content_type__app_label="core",
                content_type__model="panelscope",
            )
            .values_list("codename", flat=True)
            .distinct()
        )
        return RoleGrantRowsDTO(role_names=list(role_names), codenames=list(codenames))

    def user_ids_with_level(self, scope: Scope, level: Level) -> set[UUID]:
        """Every active user holding ``level`` or higher on ``scope``, in one query: Admin by
        group alone (it is owner of every scope without stored rows, as in ``resolve_grants``),
        the other roles through their scope codenames. Inactive users are left out — they cannot
        sign in, so nothing is sent to them.

        >>> RoleGrantRepositoryImpl().user_ids_with_level(Scope.SONGS, Level.MANAGE)
        {UUID('...admin...'), UUID('...leader...')}
        """
        by_admin = Q(groups__name=Role.ADMIN.value)
        by_codename = Q(
            groups__name__in=_ROLE_NAMES,
            groups__permissions__content_type__app_label="core",
            groups__permissions__content_type__model="panelscope",
            groups__permissions__codename__in=codenames_at_least(scope, level),
        )
        user_ids = (
            get_user_model()
            .objects.filter(is_active=True)
            .filter(by_admin | by_codename)
            .values_list("pk", flat=True)
            .distinct()
        )
        return set(user_ids)
