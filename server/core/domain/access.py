"""Roles, scopes and levels of the management panel, and the pure rules between them.

A role (Django group) holds a level on each scope it can reach; a request needs a level that
depends on its method. Design in ``specs/012-feature-role-permissions/``. No Django import here:
the permission rows and the query live in ``core.models`` and ``core.repositories``.
"""

from collections.abc import Collection, Iterable, Mapping
from enum import IntEnum, StrEnum
from types import MappingProxyType


class Role(StrEnum):
    """The value is the Django group name. Always refer to a role through this enum:
    ``"media"`` alone collides with the ``features/media`` feature name."""

    ADMIN = "admin"
    LEADER = "leader"
    MEDIA = "media"


# User-facing, so in Portuguese.
ROLE_DISPLAY_NAMES: Mapping[Role, str] = MappingProxyType(
    {Role.ADMIN: "Admin", Role.LEADER: "Liderança", Role.MEDIA: "Mídia"}
)


class Scope(StrEnum):
    """A feature area of the panel. The value is the wire name. Reports get one scope each
    (``reports.<name>``) so each report can be released to different roles."""

    MEMBERS = "members"
    SCHEDULE = "schedule"
    SONGS = "songs"
    GALLERY = "gallery"
    EVENTS = "events"
    NOTICES = "notices"
    REPORTS_HYMNAL_HISTORY = "reports.hymnal_history"


class Level(IntEnum):
    """Hierarchical: a higher level includes every lower one."""

    VIEW = 1
    MANAGE = 2
    OWNER = 3

    @property
    def wire_name(self) -> str:
        """>>> Level.MANAGE.wire_name
        'manage'
        """
        return self.name.lower()


DEFAULT_LEVEL_BY_METHOD: Mapping[str, Level] = MappingProxyType(
    {
        "GET": Level.VIEW,
        "HEAD": Level.VIEW,
        "OPTIONS": Level.VIEW,
        "POST": Level.MANAGE,
        "PUT": Level.MANAGE,
        "PATCH": Level.MANAGE,
        "DELETE": Level.OWNER,
    }
)


def codename(scope: Scope, level: Level) -> str:
    """Permission codename for a (scope, level) pair. The dot becomes "_" because Django reads
    ``"app_label.codename"`` with a dot as separator.

    >>> codename(Scope.REPORTS_HYMNAL_HISTORY, Level.VIEW)
    'reports_hymnal_history__view'
    """
    return f"{scope.value.replace('.', '_')}__{level.name.lower()}"


PERMISSION_BY_CODENAME: Mapping[str, tuple[Scope, Level]] = MappingProxyType(
    {codename(scope, level): (scope, level) for scope in Scope for level in Level}
)


def codenames_at_least(scope: Scope, level: Level) -> frozenset[str]:
    """Codenames that give ``level`` or higher on ``scope`` — levels are hierarchical, so a role
    holding ``owner`` also counts for ``manage``. Used to find every holder of a level at once
    (specs/017-sunday-setlist-push R-04).

    >>> sorted(codenames_at_least(Scope.SONGS, Level.MANAGE))
    ['songs__manage', 'songs__owner']
    """
    return frozenset(codename(scope, held) for held in Level if held >= level)


def panel_scope_permissions() -> tuple[tuple[str, str], ...]:
    """``Meta.permissions`` of ``core.PanelScope``: one entry per scope and level.

    >>> panel_scope_permissions()[0]
    ('members__view', 'members: view')
    """
    return tuple(
        (codename(scope, level), f"{scope.value}: {level.wire_name}")
        for scope in Scope
        for level in Level
    )


def required_level(method: str, overrides: Mapping[str, Level]) -> Level:
    """Level a request needs: the endpoint's override for its method, else the method default.
    An unknown method needs ``OWNER`` — fail closed.

    >>> required_level("PATCH", {"PATCH": Level.OWNER})
    <Level.OWNER: 3>
    """
    method = method.upper()
    if method in overrides:
        return overrides[method]
    return DEFAULT_LEVEL_BY_METHOD.get(method, Level.OWNER)


def validate_overrides(overrides: Mapping[str, Level]) -> None:
    """Reject an override that names an unknown method or lowers its method's default.

    Called when an endpoint's permission is declared, so the mistake fails at import instead
    of silently granting less protection (spec FR-005).

    >>> validate_overrides({"PATCH": Level.OWNER})
    """
    for method, level in overrides.items():
        default = DEFAULT_LEVEL_BY_METHOD.get(method)
        if default is None:
            allowed = ", ".join(DEFAULT_LEVEL_BY_METHOD)
            raise ValueError(f"Override for unknown method {method!r}; expected one of {allowed}.")
        if level < default:
            raise ValueError(
                f"Override {method}={level.name} is below the method default {default.name}; "
                "overrides may only raise the level."
            )


def resolve_grants(roles: Collection[Role], codenames: Iterable[str]) -> dict[Scope, Level]:
    """Highest level per scope the roles give. Scopes out of reach are absent.

    >>> resolve_grants([Role.LEADER], ["members__manage", "members__view"])
    {<Scope.MEMBERS: 'members'>: <Level.MANAGE: 2>}
    """
    # Admin is owner of every scope without reading stored permissions, so a scope added later
    # can never lock the administrator out (spec FR-008).
    if Role.ADMIN in roles:
        return {scope: Level.OWNER for scope in Scope}
    levels: dict[Scope, Level] = {}
    for name in codenames:
        grant = PERMISSION_BY_CODENAME.get(name)
        if grant is None:
            continue
        scope, level = grant
        levels[scope] = max(level, levels.get(scope, level))
    return levels
