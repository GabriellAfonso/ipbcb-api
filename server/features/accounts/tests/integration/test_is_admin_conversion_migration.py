"""Data migration 0003: `is_admin=True` becomes the Admin role (spec 012 FR-023, US1 1-2).

0003 is irreversible, so the database cannot be walked back through it. Same technique as
`features/members/tests/integration/test_birth_date_split_migration.py`: 0003 changes no schema,
so undoing the later migrations for real and marking 0003 unapplied (fake) leaves exactly the
0002 tables, where `is_admin` still exists.
"""

from collections.abc import Iterator
from typing import Any

import pytest
from django.db import connection
from django.db.migrations.exceptions import IrreversibleError
from django.db.migrations.executor import MigrationExecutor

BEFORE = ("accounts", "0002_remove_profile_active")
CONVERSION = ("accounts", "0003_is_admin_to_admin_role")


def _executor() -> MigrationExecutor:
    return MigrationExecutor(connection)


def _leaf_nodes() -> list[tuple[str, str]]:
    leaves: list[tuple[str, str]] = _executor().loader.graph.leaf_nodes()
    return leaves


def _migrate(target: tuple[str, str], fake: bool = False) -> Any:
    executor = _executor()
    executor.migrate([target], fake=fake)
    return executor.loader.project_state(target).apps


@pytest.fixture
def apps_before_conversion() -> Iterator[Any]:
    """Historical apps at 0002, with the database schema to match; back to the leaf after."""
    _migrate(CONVERSION)
    _migrate(BEFORE, fake=True)
    yield _executor().loader.project_state(BEFORE).apps
    _executor().migrate(_leaf_nodes())


def _profile_owner(apps: Any, username: str, is_admin: bool) -> Any:
    user = apps.get_model("accounts", "User").objects.create(username=username, password="x")
    apps.get_model("accounts", "Profile").objects.create(user=user, is_admin=is_admin)
    return user


@pytest.mark.django_db(transaction=True)
class TestIsAdminConversion:
    def test_admins_join_the_admin_group_and_nobody_else(self, apps_before_conversion: Any) -> None:
        admin = _profile_owner(apps_before_conversion, "old.admin", is_admin=True)
        member = _profile_owner(apps_before_conversion, "plain.user", is_admin=False)

        user_model = _migrate(CONVERSION).get_model("accounts", "User")

        assert list(user_model.objects.get(pk=admin.pk).groups.values_list("name", flat=True)) == [
            "admin"
        ]
        assert not user_model.objects.get(pk=member.pk).groups.exists()

    def test_refuses_to_run_backwards(self, apps_before_conversion: Any) -> None:
        _migrate(CONVERSION)
        with pytest.raises(IrreversibleError):
            _migrate(BEFORE)
