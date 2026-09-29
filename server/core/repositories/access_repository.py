from uuid import UUID

from django.contrib.auth.models import Group, Permission

from core.application.dtos.access_dtos import RoleGrantRowsDTO
from core.domain.access import Role

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
