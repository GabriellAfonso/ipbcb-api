"""Data migration 0005: single birth date into day, month and year (spec 011, US4).

0005 is irreversible, so the database cannot be walked back through it. The test instead
restores the 0004 schema by hand: 0005 changes no schema, so undoing the later migrations for
real and marking 0005 unapplied (fake) leaves exactly the 0004 tables.
"""

from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest
from django.db import connection
from django.db.migrations.exceptions import IrreversibleError
from django.db.migrations.executor import MigrationExecutor

BEFORE = ("members", "0004_member_birth_parts")
CONVERSION = ("members", "0005_split_birth_date")


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
    """Historical apps at 0004, with the database schema to match; back to the leaf after."""
    _migrate(CONVERSION)
    _migrate(BEFORE, fake=True)
    yield _executor().loader.project_state(BEFORE).apps
    _executor().migrate(_leaf_nodes())


@pytest.mark.django_db(transaction=True)
class TestSplitBirthDateMigration:
    def test_converts_each_kind_of_row(self, apps_before_conversion: Any) -> None:
        member_model = apps_before_conversion.get_model("members", "Member")
        full = member_model.objects.create(name="Full", birth_date=date(1990, 3, 12))
        no_year = member_model.objects.create(name="NoYear", birth_date=date(1, 7, 25))
        empty = member_model.objects.create(name="Empty", birth_date=None)

        converted = _migrate(CONVERSION).get_model("members", "Member").objects

        assert _parts(converted.get(pk=full.pk)) == (12, 3, 1990)
        assert _parts(converted.get(pk=no_year.pk)) == (25, 7, None)
        assert _parts(converted.get(pk=empty.pk)) == (None, None, None)

    def test_refuses_to_run_backwards(self, apps_before_conversion: Any) -> None:
        _migrate(CONVERSION)
        with pytest.raises(IrreversibleError):
            _migrate(BEFORE)


def _parts(member: Any) -> tuple[int | None, int | None, int | None]:
    return (member.birth_day, member.birth_month, member.birth_year)
