from uuid import uuid4

from core.application.access_service import AccessService
from core.application.dtos.access_dtos import AccessGrantsDTO
from core.domain.access import Level, Role, Scope
from core.tests.fakes import FakeRoleGrantRepository

LEADER_CODENAMES = [
    "members__manage",
    "schedule__manage",
    "songs__manage",
    "gallery__manage",
    "events__manage",
    "notices__manage",
    "reports_hymnal_history__view",
]


def _grants(role_names: list[str], codenames: list[str]) -> AccessGrantsDTO:
    return AccessService(FakeRoleGrantRepository(role_names, codenames)).grants_for(uuid4())


def test_roles_come_in_declaration_order() -> None:
    assert _grants(["media", "leader"], []).roles == [Role.LEADER, Role.MEDIA]


def test_admin_owns_every_scope_without_codenames() -> None:
    grants = _grants(["admin"], [])
    assert grants.levels == {scope: Level.OWNER for scope in Scope}


def test_leader_gets_the_leader_column() -> None:
    grants = _grants(["leader"], LEADER_CODENAMES)
    assert grants.level_for(Scope.MEMBERS) is Level.MANAGE
    assert grants.level_for(Scope.REPORTS_HYMNAL_HISTORY) is Level.VIEW
    assert not grants.allows(Scope.MEMBERS, Level.OWNER)


def test_no_role_holds_nothing() -> None:
    grants = _grants([], [])
    assert grants.roles == []
    assert grants.levels == {}
    assert not grants.allows(Scope.MEMBERS, Level.VIEW)
