"""Roles are assigned in the Django admin, through the user's groups (spec 012 US5, FR-026-027)."""

import pytest
from django.contrib import admin
from django.contrib.auth.models import Group

from conftest import make_role_client
from core.domain.access import Role
from features.accounts.models.user import User

MEMBERS_URL = "/api/admin/members/"


def _admin_fields(model: type) -> set[str]:
    fieldsets = admin.site._registry[model].fieldsets or ()
    return {str(field) for _, options in fieldsets for field in options["fields"]}


class TestAdminSite:
    def test_user_form_edits_groups(self) -> None:
        assert "groups" in _admin_fields(User)

    def test_group_admin_registered(self) -> None:
        assert admin.site.is_registered(Group)


@pytest.mark.django_db
class TestAssignment:
    def test_new_role_applies_on_the_next_request_without_login(self) -> None:
        client, user = make_role_client()
        assert client.get(MEMBERS_URL).status_code == 403

        user.groups.add(Group.objects.get(name=Role.LEADER.value))

        assert client.get(MEMBERS_URL).status_code == 200

    def test_removed_role_applies_on_the_next_request(self) -> None:
        client, user = make_role_client(Role.LEADER)
        assert client.get(MEMBERS_URL).status_code == 200

        user.groups.clear()

        assert client.get(MEMBERS_URL).status_code == 403

    def test_admin_role_does_not_open_the_django_admin(self) -> None:
        _, user = make_role_client(Role.ADMIN)
        user.refresh_from_db()
        assert user.is_staff is False
        assert user.is_superuser is False
