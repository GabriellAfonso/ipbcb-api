"""Migration 0004 adds the trash and change-feed columns without touching existing rows
(specs/014-gallery-trash-sync research R-15)."""

from collections.abc import Iterator
from typing import Any

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

BEFORE = ("gallery", "0003_backfill_positions")
TRASH = ("gallery", "0004_trash_and_change_feed")


def _migrate(target: tuple[str, str]) -> Any:
    executor = MigrationExecutor(connection)
    executor.migrate([target])
    return executor.loader.project_state(target).apps


@pytest.fixture
def apps_before() -> Iterator[Any]:
    yield _migrate(BEFORE)
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())


@pytest.mark.django_db(transaction=True)
class TestTrashSchemaMigration:
    def test_existing_rows_are_live_with_an_updated_at(self, apps_before: Any) -> None:
        album = apps_before.get_model("gallery", "Album").objects.create(name="Culto")
        apps_before.get_model("gallery", "Photo").objects.create(
            album=album, name="a.jpg", image="gallery/culto/a.jpg"
        )

        apps = _migrate(TRASH)

        for model in ("Album", "Photo"):
            row = apps.get_model("gallery", model)._base_manager.get()
            assert row.deleted_at is None
            assert row.deletion_batch_id is None
            assert row.updated_at is not None

    def test_rolls_back_to_0003_and_forward_again(self, apps_before: Any) -> None:
        apps_before.get_model("gallery", "Album").objects.create(name="Culto")
        _migrate(TRASH)
        apps = _migrate(BEFORE)
        assert apps.get_model("gallery", "Album").objects.count() == 1

        apps = _migrate(TRASH)

        assert apps.get_model("gallery", "Album")._base_manager.count() == 1
