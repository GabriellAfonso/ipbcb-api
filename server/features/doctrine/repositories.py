from typing import Protocol

from pydantic import TypeAdapter

from features.doctrine.dtos import DoctrineDocument
from features.doctrine.models import DoctrineStandard

_DOCUMENT_ADAPTER: TypeAdapter[DoctrineDocument] = TypeAdapter(DoctrineDocument)


class DoctrineRepository(Protocol):
    """Contract for doctrine document access."""

    def list_documents(self) -> list[DoctrineDocument]: ...

    def get_document(self, slug: str) -> DoctrineDocument | None: ...


class DoctrineRepositoryImpl:
    """Reads the doctrine documents from ``DoctrineStandard`` on every call.

    No cache: validating all three documents takes ~25 ms and the app revalidates with ``ETag``
    (specs/027-doctrine-database R-06).
    """

    def list_documents(self) -> list[DoctrineDocument]:
        """All documents, ordered by ``position``.

        >>> [d.slug for d in DoctrineRepositoryImpl().list_documents()][0]
        'westminster-shorter-catechism'
        """
        return [_to_document(row) for row in DoctrineStandard.objects.order_by("position")]

    def get_document(self, slug: str) -> DoctrineDocument | None:
        """The document with exactly this slug (case-sensitive), or ``None``.

        >>> DoctrineRepositoryImpl().get_document("Westminster-Shorter-Catechism") is None
        True
        """
        row = DoctrineStandard.objects.filter(slug=slug).first()
        return _to_document(row) if row else None


def _to_document(row: DoctrineStandard) -> DoctrineDocument:
    # Validated on read so a row always serves the shape the app expects; edition and year are
    # always set, so the view's exclude_unset dump keeps them as explicit nulls.
    items_key = "questions" if row.kind == "catechism" else "chapters"
    return _DOCUMENT_ADAPTER.validate_python(
        {
            "slug": row.slug,
            "title": row.title,
            "kind": row.kind,
            "position": row.position,
            "edition": row.edition or None,
            "year": row.year,
            items_key: row.content,
        }
    )
