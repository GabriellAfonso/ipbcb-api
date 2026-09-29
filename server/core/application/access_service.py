from uuid import UUID

from core.application.dtos.access_dtos import AccessGrantsDTO
from core.domain.access import Role, resolve_grants
from core.repositories.interfaces import RoleGrantRepository


class AccessService:
    """Answers which roles a user holds and which level each gives on every scope.

    Knows nothing of HTTP: turning a request method into a required level is the permission
    class's job (``core.http.permissions.scope_permission``).
    """

    def __init__(self, role_grant_repository: RoleGrantRepository) -> None:
        self._repository = role_grant_repository

    def grants_for(self, user_id: UUID) -> AccessGrantsDTO:
        """Roles in declaration order (Admin, Leader, Media) and the resulting levels.

        >>> service.grants_for(leader.pk).levels[Scope.MEMBERS]
        <Level.MANAGE: 2>
        """
        rows = self._repository.role_grants(user_id)
        held = set(rows.role_names)
        roles = [role for role in Role if role.value in held]
        return AccessGrantsDTO(roles=roles, levels=resolve_grants(roles, rows.codenames))
