"""Reads and validates doctrine document files.

The documents live in the database (specs/027-doctrine-database). These files are the frozen input
of the data migrations that load them: every rule a hand edit can break is checked here, before
anything is written, with a message that names the file, the field and the offending value
(specs/019-doctrine-documents FR-012). A correction is a new file set and a new migration; the
files of an applied migration never change.
"""

import re
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from features.doctrine.dtos import CatechismDocument, DoctrineDocument

DOCTRINE_DATA_DIR = Path(__file__).parent / "migrations" / "data"

_SLUG_PATTERN = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
_DOCUMENT_ADAPTER: TypeAdapter[DoctrineDocument] = TypeAdapter(DoctrineDocument)


class DoctrineDataError(ValueError):
    """A data file breaks a doctrine data rule. Raised only while a data migration loads the
    files, so it stops ``migrate``; it never reaches an HTTP response."""


def load_doctrine_documents(data_dir: Path) -> list[DoctrineDocument]:
    """Load every ``*.json`` in ``data_dir``, validated, ordered by ``position``.

    >>> [d.slug for d in load_doctrine_documents(DOCTRINE_DATA_DIR)]
    ['westminster-shorter-catechism', 'westminster-larger-catechism', ...]
    """
    documents = [_load_document(path) for path in sorted(data_dir.glob("*.json"))]
    _require_unique_positions(documents)
    return sorted(documents, key=lambda document: document.position)


def stored_content(document: DoctrineDocument) -> list[object]:
    """The ``questions`` or ``chapters`` list as stored in ``DoctrineStandard.content``.

    ``exclude_unset`` keeps a paragraph without a list free of ``lists``/``text_after`` while an
    explicit ``"reference": null`` stays (specs/027-doctrine-database R-02).

    >>> stored_content(shorter_catechism)[0]["number"]
    1
    """
    dumped = document.model_dump(mode="json", exclude_unset=True)
    items: list[object] = dumped["questions" if document.kind == "catechism" else "chapters"]
    return items


def _load_document(path: Path) -> DoctrineDocument:
    try:
        document = _DOCUMENT_ADAPTER.validate_json(path.read_bytes())
    except ValidationError as exc:
        raise DoctrineDataError(
            f"{path.name}: does not match the doctrine document schema "
            f"(specs/019-doctrine-documents/data-model.md):\n{exc}"
        ) from exc
    _require_slug_matches_file(document, path)
    _require_numbering(document, path.name)
    return document


def _require_slug_matches_file(document: DoctrineDocument, path: Path) -> None:
    if not _SLUG_PATTERN.fullmatch(document.slug):
        raise DoctrineDataError(
            f"{path.name}: slug is {document.slug!r}; expected lowercase words joined by "
            f"hyphens, e.g. 'westminster-shorter-catechism'"
        )
    if document.slug != path.stem:
        raise DoctrineDataError(
            f"{path.name}: slug is {document.slug!r}; expected {path.stem!r} "
            f"(the file name without .json)"
        )


def _require_numbering(document: DoctrineDocument, file_name: str) -> None:
    for field, numbers in _numberings(document):
        _require_contiguous(numbers, file_name, field)


def _numberings(document: DoctrineDocument) -> list[tuple[str, list[int]]]:
    if isinstance(document, CatechismDocument):
        return [("questions", document.item_numbers())]
    paragraphs = [
        (f"chapters[{index}].paragraphs", [paragraph.number for paragraph in chapter.paragraphs])
        for index, chapter in enumerate(document.chapters)
    ]
    return [("chapters", document.item_numbers()), *paragraphs]


def _require_contiguous(numbers: list[int], file_name: str, field: str) -> None:
    if not numbers:
        raise DoctrineDataError(f"{file_name}: {field} is empty; expected items numbered 1..N")
    expected_and_found = zip(range(1, len(numbers) + 1), numbers)
    mismatch = next(((e, n) for e, n in expected_and_found if e != n), None)
    if mismatch is None:
        return
    expected, number = mismatch
    raise DoctrineDataError(
        f"{file_name}: {field}[{expected - 1}].number is {number}; expected {expected} "
        f"(numbering must be 1..N with no gaps or repeats)"
    )


def _require_unique_positions(documents: list[DoctrineDocument]) -> None:
    owner_by_position: dict[int, str] = {}
    for document in documents:
        owner = owner_by_position.setdefault(document.position, document.slug)
        if owner != document.slug:
            raise DoctrineDataError(
                f"{owner}.json and {document.slug}.json: both have position "
                f"{document.position}; expected a different list position per document"
            )
