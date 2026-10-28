from core.domain.exceptions import DoctrineDocumentNotFoundError
from features.doctrine.dtos import CatechismDocument, DoctrineDocument, DoctrineDocumentSummary
from features.doctrine.repositories import DoctrineRepository


class DoctrineService:
    """Application logic for the read-only doctrine documents."""

    def __init__(self, doctrine_repository: DoctrineRepository) -> None:
        self._repo = doctrine_repository

    def list_documents(self) -> list[DoctrineDocumentSummary]:
        """One summary per document, in list order.

        >>> service.list_documents()[0].item_count
        107
        """
        return [_summarize(document) for document in self._repo.list_documents()]

    def get_document(self, slug: str) -> DoctrineDocument:
        """The full document, or raise DoctrineDocumentNotFoundError.

        >>> service.get_document("westminster-confession-of-faith").kind
        'confession'
        """
        document = self._repo.get_document(slug)
        if document is None:
            raise DoctrineDocumentNotFoundError(slug)
        return document


def _summarize(document: DoctrineDocument) -> DoctrineDocumentSummary:
    # Questions for a catechism, chapters for a confession (spec FR-016).
    if isinstance(document, CatechismDocument):
        item_count = len(document.questions)
    else:
        item_count = len(document.chapters)
    return DoctrineDocumentSummary(
        slug=document.slug,
        title=document.title,
        kind=document.kind,
        edition=document.edition,
        year=document.year,
        item_count=item_count,
    )
