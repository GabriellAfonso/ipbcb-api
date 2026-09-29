"""Migrations 0005 and 0006 seed the three roles with the spec 012 matrix (spec FR-025, US1
scenario 5), with `gallery` raised to `owner` for Liderança and Mídia by feature 013.

The test database is built by running every migration, so what it holds is what a fresh
deploy holds. The expected table is written here, not imported from application code, so a
change to the code cannot silently change what the test expects.
"""

import pytest
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command

EXPECTED_ROLE_CODENAMES = {
    "admin": set(),
    "leader": {
        "members__manage",
        "schedule__manage",
        "songs__manage",
        "gallery__owner",
        "events__manage",
        "notices__manage",
        "reports_hymnal_history__view",
    },
    "media": {
        "gallery__owner",
        "events__manage",
        "notices__manage",
        "reports_hymnal_history__view",
    },
}


def _panel_permissions() -> list[Permission]:
    return list(
        Permission.objects.filter(content_type__app_label="core", content_type__model="panelscope")
    )


def _role_codenames() -> dict[str, set[str]]:
    return {
        group.name: {p.codename for p in group.permissions.filter(content_type__model="panelscope")}
        for group in Group.objects.all()
    }


@pytest.mark.django_db
class TestPanelRolesSeed:
    def test_groups_hold_exactly_the_matrix(self) -> None:
        assert _role_codenames() == EXPECTED_ROLE_CODENAMES

    def test_permission_rows_exist_once_each(self) -> None:
        codenames = [p.codename for p in _panel_permissions()]
        assert len(codenames) == 21
        assert len(set(codenames)) == 21

    def test_migrating_again_changes_nothing(self) -> None:
        call_command("migrate", verbosity=0)
        assert _role_codenames() == EXPECTED_ROLE_CODENAMES
        assert len(_panel_permissions()) == 21
