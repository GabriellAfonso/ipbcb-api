"""Migration 0008 raises Liderança and Mídia to `owner` on `events`, and rolls back
(specs/020-church-events FR-014, research R-11)."""

import importlib
from collections.abc import Iterator
from typing import Any

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

BEFORE = ("core", "0007_devicetoken")
RAISE = ("core", "0008_events_owner_for_leader_media")
seed_migration = importlib.import_module("core.migrations.0005_seed_panel_roles")
gallery_migration = importlib.import_module("core.migrations.0006_gallery_owner_for_leader_media")


def _migrate(target: tuple[str, str]) -> Any:
    executor = MigrationExecutor(connection)
    executor.migrate([target])
    return executor.loader.project_state(target).apps


@pytest.fixture
def back_to_leaf() -> Iterator[None]:
    """Start at 0007 with the groups as 0005 + 0006 leave them. A transactional test flushes
    every table afterwards, groups included, and 0005 cannot be unapplied, so their forwards are
    run directly instead (same approach as test_gallery_owner_migration)."""
    apps = _migrate(BEFORE)
    seed_migration.forward(apps, None)
    gallery_migration.forward(apps, None)
    yield
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())


def _codenames(apps: Any, role: str) -> set[str]:
    group = apps.get_model("auth", "Group").objects.get(name=role)
    return set(group.permissions.values_list("codename", flat=True))


@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("back_to_leaf")
class TestEventsOwnerMigration:
    @pytest.mark.parametrize("role", ["leader", "media"])
    def test_forward_swaps_manage_for_owner(self, role: str) -> None:
        before = _codenames(_migrate(BEFORE), role)
        assert "events__manage" in before

        after = _codenames(_migrate(RAISE), role)

        assert after == (before - {"events__manage"}) | {"events__owner"}

    @pytest.mark.parametrize("role", ["leader", "media"])
    def test_backward_restores_manage(self, role: str) -> None:
        raised = _codenames(_migrate(RAISE), role)

        restored = _codenames(_migrate(BEFORE), role)

        assert restored == (raised - {"events__owner"}) | {"events__manage"}

    def test_admin_still_holds_nothing_stored(self) -> None:
        assert _codenames(_migrate(RAISE), "admin") == set()
