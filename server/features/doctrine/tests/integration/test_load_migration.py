"""The Westminster Standards load migration, forward and back (specs/027-doctrine-database US2).

The test database is built by running every migration, so the forward step already ran; the
functions are called again here with the live app registry to check the reverse and a re-run.
"""

import json
from importlib import import_module

import pytest
from django.apps import apps

from features.doctrine.loading import DOCTRINE_DATA_DIR
from features.doctrine.models import DoctrineStandard

load = import_module("features.doctrine.migrations.0002_load_westminster_standards")

pytestmark = pytest.mark.django_db

SLUGS = [
    "westminster-shorter-catechism",
    "westminster-larger-catechism",
    "westminster-confession-of-faith",
]


def test_fresh_database_holds_the_three_documents() -> None:
    rows = list(DoctrineStandard.objects.order_by("position"))

    assert [(row.position, row.slug) for row in rows] == list(zip([1, 2, 3], SLUGS))
    assert {(row.edition, row.year) for row in rows} == {("", None)}


@pytest.mark.parametrize("slug", SLUGS)
def test_stored_content_equals_the_frozen_file(slug: str) -> None:
    # Compared with the raw file, not a DTO dump, so nothing the load does can hide a change.
    raw = json.loads((DOCTRINE_DATA_DIR / f"{slug}.json").read_text(encoding="utf-8"))
    items = raw["questions"] if raw["kind"] == "catechism" else raw["chapters"]

    assert DoctrineStandard.objects.get(slug=slug).content == items


def test_reverse_removes_only_what_it_created() -> None:
    kept = DoctrineStandard.objects.create(
        slug="other-document", title="Outro", kind="catechism", position=9, content=[]
    )

    load.backward(apps, None)

    assert list(DoctrineStandard.objects.values_list("pk", flat=True)) == [kept.pk]


def test_reverse_then_forward_restores_the_load() -> None:
    load.backward(apps, None)
    assert not DoctrineStandard.objects.exists()

    load.forward(apps, None)

    assert list(DoctrineStandard.objects.values_list("slug", flat=True)) == SLUGS
