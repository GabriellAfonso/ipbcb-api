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
                "item_count": 2,
            },
            {
                "slug": "tiny-confession",
                "title": "Confissão de Teste",
                "kind": "confession",
                "item_count": 2,
            },
        ]

    def test_empty_repository_lists_nothing(self) -> None:
        assert DoctrineService(FakeDoctrineRepository([])).list_documents() == []


class TestGetDocument:
    def test_returns_document_by_slug(self, service: DoctrineService) -> None:
        assert service.get_document("tiny-confession").kind == "confession"

    @pytest.mark.parametrize("slug", ["nope", "Tiny-Catechism"])
    def test_unknown_or_wrong_case_slug_raises(self, service: DoctrineService, slug: str) -> None:
        with pytest.raises(DoctrineDocumentNotFoundError, match=f"'{slug}'"):
            service.get_document(slug)
