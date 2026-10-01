"""Only the three role groups and their scope permissions count (spec 012 FR-030, research R-10)."""

from uuid import UUID

import pytest
from django.contrib.auth.models import Group, Permission

from conftest import make_user
from core.domain.access import Level, Role, Scope
from features.accounts.models.user import User
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


def _user_in(username: str, *group_names: str) -> User:
    user = make_user(username=username)
    user.groups.add(*Group.objects.filter(name__in=group_names))
    return user


@pytest.mark.django_db
class TestUserIdsWithLevel:
    """Who holds ``manage`` on ``songs`` — reminder recipients (spec 017 R-04)."""

    repository = RoleGrantRepositoryImpl()

    def _holders(self) -> set[UUID]:
        return self.repository.user_ids_with_level(Scope.SONGS, Level.MANAGE)

    def test_admin_counts_without_stored_permission(self) -> None:
        admin = _user_in("admin", Role.ADMIN.value)
        assert self._holders() == {admin.pk}

    def test_leader_counts_through_its_codename(self) -> None:
        leader = _user_in("leader", Role.LEADER.value)
        assert self._holders() == {leader.pk}

    def test_media_does_not_count(self) -> None:
        _user_in("media", Role.MEDIA.value)
        assert self._holders() == set()

    def test_unrelated_group_with_the_codename_does_not_count(self) -> None:
        editors = Group.objects.create(name="editors")
        editors.permissions.add(_panel_permission("songs__owner"))
        _user_in("editor", "editors")
        assert self._holders() == set()

    def test_inactive_user_does_not_count(self) -> None:
        admin = _user_in("admin", Role.ADMIN.value)
        admin.is_active = False
        admin.save()
        assert self._holders() == set()

    def test_superuser_without_role_does_not_count(self) -> None:
        root = make_user(username="root")
        root.is_superuser = True
        root.save()
        assert self._holders() == set()

    def test_user_with_two_roles_appears_once(self) -> None:
        both = _user_in("both", Role.ADMIN.value, Role.LEADER.value)
        assert self._holders() == {both.pk}
