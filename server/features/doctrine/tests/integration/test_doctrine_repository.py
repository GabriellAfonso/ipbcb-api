"""``DoctrineRepositoryImpl`` against the table (specs/027-doctrine-database R-02, R-06)."""

import pytest

from features.doctrine.dtos import CatechismDocument, ConfessionDocument
from features.doctrine.models import DoctrineStandard
from features.doctrine.repositories import DoctrineRepositoryImpl
from features.doctrine.tests.integration.conftest import ServedFixtureDocuments

pytestmark = pytest.mark.usefixtures("fixture_doctrine")


def test_lists_documents_by_position() -> None:
    DoctrineStandard.objects.filter(slug="tiny-confession").update(position=0)
    slugs = [document.slug for document in DoctrineRepositoryImpl().list_documents()]
    assert slugs == ["tiny-confession", "tiny-catechism"]


@pytest.mark.parametrize("slug", ["nope", "Tiny-Catechism"])
def test_unknown_or_wrong_case_slug_is_none(slug: str) -> None:
    assert DoctrineRepositoryImpl().get_document(slug) is None


def test_paragraph_without_list_keeps_keys_unset() -> None:
    confession = DoctrineRepositoryImpl().get_document("tiny-confession")
    assert isinstance(confession, ConfessionDocument)
    dumped = confession.chapters[0].paragraphs[0].model_dump(exclude_unset=True)
    assert set(dumped) == {"number", "text"}


def test_uninterpreted_reference_stays_null() -> None:
    catechism = DoctrineRepositoryImpl().get_document("tiny-catechism")
    assert isinstance(catechism, CatechismDocument)
    proof = catechism.questions[0].proof_texts[2].model_dump(exclude_unset=True)
    assert proof == {"printed": "Sl 86-8", "reference": None}


def test_empty_edition_reads_as_none() -> None:
    document = DoctrineRepositoryImpl().get_document("tiny-catechism")
    assert document is not None
    assert (document.edition, document.year) == (None, None)
    assert {"edition", "year"} <= document.model_fields_set


def test_round_trip_equals_the_fixture_file(fixture_doctrine: ServedFixtureDocuments) -> None:
    document = DoctrineRepositoryImpl().get_document("tiny-confession")
    assert document is not None
    stored = (fixture_doctrine.data_dir / "tiny-confession.json").read_text(encoding="utf-8")
    expected = ConfessionDocument.model_validate_json(stored)
    assert document.model_dump(exclude_unset=True) == {
        **expected.model_dump(exclude_unset=True),
        "edition": None,
        "year": None,
    }


def test_empty_table_lists_nothing() -> None:
    DoctrineStandard.objects.all().delete()
    assert DoctrineRepositoryImpl().list_documents() == []
