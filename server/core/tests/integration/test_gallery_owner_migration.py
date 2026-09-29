"""Migration 0006 raises Liderança and Mídia to `owner` on `gallery`, and rolls back
(specs/013-gallery-write-api FR-003, research R-10)."""

import importlib
from collections.abc import Iterator
from typing import Any

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

SEED = ("core", "0005_seed_panel_roles")
RAISE = ("core", "0006_gallery_owner_for_leader_media")
seed_migration = importlib.import_module("core.migrations.0005_seed_panel_roles")


def _migrate(target: tuple[str, str]) -> Any:
    executor = MigrationExecutor(connection)
    executor.migrate([target])
    return executor.loader.project_state(target).apps


@pytest.fixture
def back_to_leaf() -> Iterator[None]:
    """Start at 0005 with its groups re-seeded. A transactional test flushes every table
    afterwards, groups included, and 0005 cannot be unapplied (accounts 0003, irreversible,
    depends on it), so its get-or-create forward is run directly instead."""
    seed_migration.forward(_migrate(SEED), None)
    yield
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())


def _codenames(apps: Any, role: str) -> set[str]:
    group = apps.get_model("auth", "Group").objects.get(name=role)
    return set(group.permissions.values_list("codename", flat=True))


@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("back_to_leaf")
class TestGalleryOwnerMigration:
    @pytest.mark.parametrize("role", ["leader", "media"])
    def test_forward_swaps_manage_for_owner(self, role: str) -> None:
        before = _codenames(_migrate(SEED), role)

        after = _codenames(_migrate(RAISE), role)

        assert after == (before - {"gallery__manage"}) | {"gallery__owner"}

    @pytest.mark.parametrize("role", ["leader", "media"])
    def test_backward_restores_manage(self, role: str) -> None:
        raised = _codenames(_migrate(RAISE), role)

        restored = _codenames(_migrate(SEED), role)

        assert restored == (raised - {"gallery__owner"}) | {"gallery__manage"}

    def test_admin_still_holds_nothing_stored(self) -> None:
        assert _codenames(_migrate(RAISE), "admin") == set()
