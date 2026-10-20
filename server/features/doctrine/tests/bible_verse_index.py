"""Test-only index of which Bible chapters and verses exist (specs/019-doctrine-documents R-04).

It reads the Bible data files by path instead of importing ``features.bible``, so the doctrine
feature never depends on the Bible feature (constitution: features never import each other).
"""

import json
from pathlib import Path

from features.doctrine.dtos import BibleReference

BIBLE_DATA_FILES = sorted((Path(__file__).resolve().parents[2] / "bible" / "data").glob("*.json"))

_ChapterKey = tuple[str, int]


class BibleVerseIndex:
    """Verse count per (book, chapter), the minimum across every Bible version given, so a
    reference that passes exists in all of them (clarification Q3)."""

    def __init__(self, verse_counts: dict[_ChapterKey, int]) -> None:
        self._verse_counts = verse_counts
        self._books = {book for book, _ in verse_counts}

    @classmethod
    def from_files(cls, paths: list[Path]) -> "BibleVerseIndex":
        """Build the index from Bible JSON files (format in specs/bible/spec.md).

        >>> BibleVerseIndex.from_files(BIBLE_DATA_FILES).has_book("1Tn")
        True
        """
        per_version = [_verse_counts(path) for path in paths]
        shared = (
            set.intersection(*(set(counts) for counts in per_version)) if per_version else set()
        )
        return cls({key: min(counts[key] for counts in per_version) for key in shared})

    def has_book(self, book: str) -> bool:
        return book in self._books

    def missing_verses(self, reference: BibleReference) -> str | None:
        """Why ``reference`` doesn't exist in every version, or ``None`` when it does.

        >>> index.missing_verses(BibleReference(book="Rm", chapter=11, verses=[]))
        """
        verse_count = self._verse_counts.get((reference.book, reference.chapter))
        if verse_count is None:
            return f"{reference.book} {reference.chapter} is not a chapter in every version"
        last_verse = max((span.end for span in reference.verses), default=0)
        if last_verse <= verse_count:
            return None
        return (
            f"{reference.book} {reference.chapter} has {verse_count} verses in every version; "
            f"got verse {last_verse}"
        )


def _verse_counts(path: Path) -> dict[_ChapterKey, int]:
    # utf-8-sig reads plain UTF-8 too; it only tolerates a BOM if a new version file has one.
    books: list[dict[str, object]] = json.loads(path.read_text(encoding="utf-8-sig"))
    return {
        (str(book["abbrev"]), number): len(verses)
        for book in books
        for number, verses in enumerate(_chapters(book), start=1)
    }


def _chapters(book: dict[str, object]) -> list[list[object]]:
    chapters = book["chapters"]
    assert isinstance(chapters, list)
    return chapters
