"""Only the three role groups and their scope permissions count (spec 012 FR-030, research R-10)."""

import pytest
from django.contrib.auth.models import Group, Permission

from conftest import make_user
from core.repositories.access_repository import RoleGrantRepositoryImpl

LEADER_CODENAMES = {
    "members__manage",
    "schedule__manage",
    "songs__manage",
    # Raised from manage by core/0006 (specs/013-gallery-write-api FR-003).
    "gallery__owner",
    "events__manage",
    "notices__manage",
    "reports_hymnal_history__view",
}


def _panel_permission(codename: str) -> Permission:
    return Permission.objects.get(content_type__model="panelscope", codename=codename)


@pytest.mark.django_db
class TestRoleGrantRepository:
    repository = RoleGrantRepositoryImpl()

    def test_leader_reads_its_group_and_codenames(self) -> None:
        user = make_user(username="leader")
        user.groups.add(Group.objects.get(name="leader"))
        rows = self.repository.role_grants(user.pk)
        assert rows.role_names == ["leader"]
        assert set(rows.codenames) == LEADER_CODENAMES

    def test_superuser_without_role_gets_nothing(self) -> None:
        user = make_user(username="root")
        user.is_superuser = True
        user.is_staff = True
        user.save()
        rows = self.repository.role_grants(user.pk)
        assert rows.role_names == []
        assert rows.codenames == []

    def test_other_group_grants_nothing(self) -> None:
        editors = Group.objects.create(name="editors")
        editors.permissions.add(_panel_permission("members__owner"))
        user = make_user(username="editor")
        user.groups.add(editors)
        rows = self.repository.role_grants(user.pk)
        assert rows.role_names == []
        assert rows.codenames == []

    def test_direct_user_permission_grants_nothing(self) -> None:
        user = make_user(username="direct")
        user.user_permissions.add(_panel_permission("members__owner"))
        assert self.repository.role_grants(user.pk).codenames == []

    def test_only_panel_scope_permissions_are_read(self) -> None:
        leader = Group.objects.get(name="leader")
        leader.permissions.add(Permission.objects.get(codename="view_user"))
        user = make_user(username="leader2")
        user.groups.add(leader)
        assert set(self.repository.role_grants(user.pk).codenames) == LEADER_CODENAMES
