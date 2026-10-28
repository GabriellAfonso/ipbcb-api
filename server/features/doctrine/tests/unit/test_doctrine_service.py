from pathlib import Path

import pytest

from core.domain.exceptions import DoctrineDocumentNotFoundError
from features.doctrine.loading import load_doctrine_documents
from features.doctrine.services import DoctrineService
from features.doctrine.tests.fakes import FakeDoctrineRepository
from features.doctrine.tests.fixture_dirs import FIXTURES_DIR


@pytest.fixture
def service() -> DoctrineService:
    documents = load_doctrine_documents(Path(FIXTURES_DIR / "valid"))
    return DoctrineService(FakeDoctrineRepository(documents))


class TestListDocuments:
    def test_summaries_follow_repository_order(self, service: DoctrineService) -> None:
        summaries = [s.model_dump() for s in service.list_documents()]
        assert summaries == [
            {
                "slug": "tiny-catechism",
                "title": "Catecismo de Teste",
                "kind": "catechism",
                "edition": None,
                "year": None,
                "item_count": 2,
            },
            {
                "slug": "tiny-confession",
                "title": "Confissão de Teste",
                "kind": "confession",
                "edition": None,
                "year": None,
                "item_count": 2,
            },
        ]

    def test_summary_carries_edition_and_year(self) -> None:
        documents = load_doctrine_documents(Path(FIXTURES_DIR / "valid"))
        known = documents[0].model_copy(update={"edition": "Edição IPB", "year": 1647})
        summary = DoctrineService(FakeDoctrineRepository([known])).list_documents()[0]
        assert (summary.edition, summary.year) == ("Edição IPB", 1647)

    def test_empty_repository_lists_nothing(self) -> None:
        assert DoctrineService(FakeDoctrineRepository([])).list_documents() == []


class TestGetDocument:
    def test_returns_document_by_slug(self, service: DoctrineService) -> None:
        assert service.get_document("tiny-confession").kind == "confession"

    @pytest.mark.parametrize("slug", ["nope", "Tiny-Catechism"])
    def test_unknown_or_wrong_case_slug_raises(self, service: DoctrineService, slug: str) -> None:
        with pytest.raises(DoctrineDocumentNotFoundError, match=f"'{slug}'"):
            service.get_document(slug)
