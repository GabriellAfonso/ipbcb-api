"""Puts doctrine documents in the table for tests, the way the load migration does.

Test-only: production rows come only from data migrations (specs/027-doctrine-database FR-007).
"""

from features.doctrine.dtos import DoctrineDocument
from features.doctrine.loading import stored_content
from features.doctrine.models import DoctrineStandard


def store_documents(documents: list[DoctrineDocument]) -> None:
    """Replace every ``DoctrineStandard`` row with ``documents``.

    >>> store_documents(load_doctrine_documents(FIXTURES_DIR / "valid"))
    """
    DoctrineStandard.objects.all().delete()
    DoctrineStandard.objects.bulk_create(
        DoctrineStandard(
            slug=document.slug,
            title=document.title,
            kind=document.kind,
            position=document.position,
            edition=document.edition or "",
            year=document.year,
            content=stored_content(document),
        )
        for document in documents
    )
