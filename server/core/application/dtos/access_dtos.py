from pydantic import ConfigDict

from core.application.dtos.strict_base import StrictBaseModel
from core.domain.access import Level, Role, Scope


class AccessGrantsDTO(StrictBaseModel):
    """What a user may do in the management panel: their roles and their level per scope.
    Scopes out of reach are absent from ``levels``.

    >>> AccessGrantsDTO(roles=[Role.MEDIA], levels={Scope.GALLERY: Level.MANAGE}).allows(
    ...     Scope.GALLERY, Level.VIEW)
    True
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    roles: list[Role]
    levels: dict[Scope, Level]

    def level_for(self, scope: Scope) -> Level | None:
        """>>> AccessGrantsDTO(roles=[], levels={}).level_for(Scope.MEMBERS) is None
        True
        """
        return self.levels.get(scope)

    def allows(self, scope: Scope, level: Level) -> bool:
        """Whether the user holds ``level`` or higher on ``scope``.

        >>> AccessGrantsDTO(roles=[], levels={}).allows(Scope.MEMBERS, Level.VIEW)
        False
        """
        held = self.level_for(scope)
        return held is not None and held >= level


class RoleGrantRowsDTO(StrictBaseModel):
    """Raw rows read for one user: the role group names they belong to and the scope
    permission codenames those groups hold. Resolution into levels happens in the service.

    >>> RoleGrantRowsDTO(role_names=["leader"], codenames=["members__manage"])
    """

    role_names: list[str]
    codenames: list[str]
