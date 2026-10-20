from pathlib import Path
from typing import Protocol

from features.doctrine.dtos import DoctrineDocument
from features.doctrine.loading import DOCTRINE_DATA_DIR, load_doctrine_documents


class DoctrineRepository(Protocol):
    """Contract for doctrine document access."""

    def list_documents(self) -> list[DoctrineDocument]: ...

    def get_document(self, slug: str) -> DoctrineDocument | None: ...


class DoctrineRepositoryImpl:
    """Loads the doctrine JSON files once, at construction, and serves them from memory."""

    def __init__(self, data_dir: Path = DOCTRINE_DATA_DIR) -> None:
        self._documents = load_doctrine_documents(data_dir)
        self._by_slug = {document.slug: document for document in self._documents}

    def list_documents(self) -> list[DoctrineDocument]:
        """All documents, ordered by ``position``.

        >>> [d.slug for d in DoctrineRepositoryImpl().list_documents()][0]
        'westminster-shorter-catechism'
        """
        return list(self._documents)

    def get_document(self, slug: str) -> DoctrineDocument | None:
        """The document with exactly this slug (case-sensitive), or ``None``.

        >>> DoctrineRepositoryImpl().get_document("Westminster-Shorter-Catechism") is None
        True
        """
        return self._by_slug.get(slug)
