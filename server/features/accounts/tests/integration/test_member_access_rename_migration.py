"""Hand-written migration 0006: `is_member` becomes `member_access` keeping every value, both
ways (specs/022-access-requests R-01; constitution §5 — a generated rename would drop them)."""

from collections.abc import Iterator
from typing import Any

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

BEFORE = ("accounts", "0005_profile_member")
RENAME = ("accounts", "0006_rename_is_member_member_access")


def _executor() -> MigrationExecutor:
    return MigrationExecutor(connection)


def _migrate(target: tuple[str, str]) -> Any:
    executor = _executor()
    executor.migrate([target])
    return executor.loader.project_state(target).apps


@pytest.fixture
def apps_before_rename() -> Iterator[Any]:
    """Historical apps at 0005, with the schema to match; back to the leaf after."""
    apps = _migrate(BEFORE)
    yield apps
    executor = _executor()
    executor.migrate(executor.loader.graph.leaf_nodes())


def _flags(apps: Any, field: str) -> dict[str, bool]:
    profiles = apps.get_model("accounts", "Profile").objects.select_related("user")
    return {profile.user.username: getattr(profile, field) for profile in profiles}


@pytest.mark.django_db(transaction=True)
class TestMemberAccessRename:
    def test_values_survive_forward_and_back(self, apps_before_rename: Any) -> None:
        user_model = apps_before_rename.get_model("accounts", "User")
        profile_model = apps_before_rename.get_model("accounts", "Profile")
        for username, flag in (("member", True), ("visitor", False)):
            user = user_model.objects.create(username=username, password="x")
            profile_model.objects.create(user=user, is_member=flag)

        after = _migrate(RENAME)
        assert _flags(after, "member_access") == {"member": True, "visitor": False}

        back = _migrate(BEFORE)
        assert _flags(back, "is_member") == {"member": True, "visitor": False}
