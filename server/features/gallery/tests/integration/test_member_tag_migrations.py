"""The two generated migrations of feature 015 apply and roll back cleanly: ``gallery 0005``
adds the tag table, ``accounts 0005`` the profile's member column (specs/015-gallery-member-tags
research R-12, quickstart §3). The production-dump run is quickstart §3; this pins the shape."""

from collections.abc import Iterator

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

BEFORE = [("gallery", "0004_trash_and_change_feed"), ("accounts", "0004_remove_profile_is_admin")]
AFTER = [("gallery", "0005_phototag"), ("accounts", "0005_profile_member")]


def _migrate(targets: list[tuple[str, str]]) -> None:
    MigrationExecutor(connection).migrate(targets)


def _tables() -> set[str]:
    return set(connection.introspection.table_names())


def _profile_columns() -> set[str]:
    with connection.cursor() as cursor:
        description = connection.introspection.get_table_description(cursor, "accounts_profile")
    return {column.name for column in description}


@pytest.fixture
def back_to_leaf() -> Iterator[None]:
    yield
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())


@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("back_to_leaf")
class TestMemberTagMigrations:
    def test_rollback_removes_table_and_column(self) -> None:
        _migrate(BEFORE)

        assert "gallery_phototag" not in _tables()
        assert "member_id" not in _profile_columns()

    def test_forward_again_restores_them(self) -> None:
        _migrate(BEFORE)
        _migrate(AFTER)

        assert "gallery_phototag" in _tables()
        assert "member_id" in _profile_columns()
