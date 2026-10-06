from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from core.application.access_service import AccessService
from core.application.dtos.access_dtos import AccessGrantsDTO
from core.domain.access import Level, Scope
from core.http import permissions as permissions_module
from core.http.permissions import scope_permission
from core.tests.fakes import FakeRoleGrantRepository

LEADER = FakeRoleGrantRepository(["leader"], ["members__manage", "reports_hymnal_history__view"])
MEDIA = FakeRoleGrantRepository(["media"], ["gallery__manage"])
ADMIN = FakeRoleGrantRepository(["admin"], [])


def _use(monkeypatch: pytest.MonkeyPatch, repository: FakeRoleGrantRepository) -> None:
    service = AccessService(repository)

    def grants_for(user_id: UUID) -> AccessGrantsDTO:
        return service.grants_for(user_id)

    monkeypatch.setattr(permissions_module, "_grants_for", grants_for)


def _request(method: str, is_authenticated: bool = True) -> MagicMock:
    request = MagicMock()
    request.method = method
    request.user.is_authenticated = is_authenticated
    request.user.pk = uuid4()
    return request


def _allowed(permission_class: type, method: str) -> bool:
    return bool(permission_class().has_permission(_request(method), MagicMock()))


class TestMembersScope:
    permission = scope_permission(Scope.MEMBERS)

    @pytest.mark.parametrize("method", ["GET", "POST", "PUT", "PATCH"])
    def test_leader_reads_and_writes(self, monkeypatch: pytest.MonkeyPatch, method: str) -> None:
        _use(monkeypatch, LEADER)
        assert _allowed(self.permission, method)

    def test_leader_cannot_delete(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _use(monkeypatch, LEADER)
        assert not _allowed(self.permission, "DELETE")

    def test_media_cannot_read(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _use(monkeypatch, MEDIA)
        assert not _allowed(self.permission, "GET")

    def test_anonymous_denied_without_reading_roles(self, monkeypatch: pytest.MonkeyPatch) -> None:
        repository = FakeRoleGrantRepository(["admin"], [])
        _use(monkeypatch, repository)
        request = _request("GET", is_authenticated=False)
        assert not self.permission().has_permission(request, MagicMock())
        assert repository.calls == []


class TestOverride:
    permission = scope_permission(Scope.REPORTS_HYMNAL_HISTORY, {"PATCH": Level.OWNER})

    def test_leader_cannot_patch_configuration(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _use(monkeypatch, LEADER)
        assert not _allowed(self.permission, "PATCH")
        assert _allowed(self.permission, "GET")

    def test_admin_can(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _use(monkeypatch, ADMIN)
        assert _allowed(self.permission, "PATCH")


def test_override_below_default_fails_when_declared() -> None:
    with pytest.raises(ValueError, match="DELETE=VIEW"):
        scope_permission(Scope.SONGS, {"DELETE": Level.VIEW})


class TestLowered:
    permission = scope_permission(Scope.SONGS, {"DELETE": Level.MANAGE}, lowered={"DELETE"})

    def test_manage_holder_can_delete(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _use(monkeypatch, FakeRoleGrantRepository(["leader"], ["songs__manage"]))
        assert _allowed(self.permission, "DELETE")

    def test_view_holder_cannot_delete(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _use(monkeypatch, FakeRoleGrantRepository(["media"], ["songs__view"]))
        assert not _allowed(self.permission, "DELETE")


def test_class_name_names_the_scope() -> None:
    assert scope_permission(Scope.SONGS).__name__ == "ScopePermission_SONGS"
