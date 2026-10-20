from features.doctrine.dtos import DoctrineDocument


class FakeDoctrineRepository:
    """In-memory ``DoctrineRepository``. Implements the whole protocol because mypy checks tests
    against it; documents are kept in the order given, like the real one after sorting."""

    def __init__(self, documents: list[DoctrineDocument]) -> None:
        self._documents = list(documents)

    def list_documents(self) -> list[DoctrineDocument]:
        return list(self._documents)

    def get_document(self, slug: str) -> DoctrineDocument | None:
        return next((d for d in self._documents if d.slug == slug), None)
