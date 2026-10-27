import json
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from features.bible.domain.canon import BibleCanon
from features.bible.dtos import BibleBook

_DATA_DIR = Path(__file__).parent.parent / "data"


class BibleRepository(Protocol):
    """Contract for Bible data access."""

    def list_versions(self) -> list[str]: ...

    def get_version(self, name: str) -> list[BibleBook] | None: ...

    def canon(self) -> BibleCanon:
        """The books and chapter counts every translation shares."""
        ...


class BibleRepositoryImpl:
    """Loads Bible data from static JSON files at construction time."""

    def __init__(self) -> None:
        self._bibles: dict[str, list[BibleBook]] = {}
        self._load()
        self._canon = BibleCanon(shared_chapter_counts(self._bibles))

    def _load(self) -> None:
        for path in _DATA_DIR.glob("*.json"):
            with path.open(encoding="utf-8") as f:
                raw: list[dict[str, object]] = json.load(f)
            self._bibles[path.stem] = [BibleBook.model_validate(book) for book in raw]

    def list_versions(self) -> list[str]:
        return sorted(self._bibles.keys())

    def get_version(self, name: str) -> list[BibleBook] | None:
        books = self._bibles.get(name)
        if books is None:
            return None
        return books

    def canon(self) -> BibleCanon:
        return self._canon


def shared_chapter_counts(bibles: Mapping[str, list[BibleBook]]) -> dict[str, int]:
    """Books in order with their chapter counts, which every translation must agree on: videos
    and progress point at a book and chapter whatever the translation (specs/025-bible-videos).

    >>> shared_chapter_counts({"NAA": naa_books, "ARA": ara_books})["Gn"]
    50
    """
    layouts = {name: [(b.abbrev, len(b.chapters)) for b in books] for name, books in bibles.items()}
    distinct = {tuple(layout) for layout in layouts.values()}
    if len(distinct) > 1:
        raise ValueError(
            f"Translations {sorted(layouts)} disagree on books or chapter counts; "
            "expected the same books, in the same order, with the same chapters."
        )
    return dict(next(iter(layouts.values()), []))
