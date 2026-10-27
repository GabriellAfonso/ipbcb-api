"""Which Bible books, chapters and verses exist, and the facts a book card shows
(specs/026-sunday-school R-02, R-03).

Pure: built in ``config/di.py`` from plain mappings the Bible repository exposes, so this feature
never imports the Bible feature. Verse counts are the minimum across translations, so a reference
that passes exists in every translation the app offers.
"""

from collections.abc import Mapping, Sequence
from typing import NamedTuple


class VerseRange(NamedTuple):
    start: int
    end: int


class BookFacts(NamedTuple):
    """What the ``book_facts`` card derives from the Bible: never typed by the editor."""

    name: str
    position: int
    chapters: int
    verses: int


class ScriptureIndex:
    """Books in canonical order with their verse counts per chapter.

    >>> index = ScriptureIndex({"Gn": [31, 25]}, {"Gn": "Gênesis"})
    >>> index.missing_passage("Gn", 2, [VerseRange(1, 26)])
    'Gn 2 tem 25 versículos; recebido o versículo 26'
    """

    def __init__(self, verse_counts: Mapping[str, Sequence[int]], names: Mapping[str, str]) -> None:
        self._verse_counts = {book: list(counts) for book, counts in verse_counts.items()}
        self._names = dict(names)
        self._positions = {book: index for index, book in enumerate(self._verse_counts, start=1)}

    def has_book(self, book: str) -> bool:
        return book in self._verse_counts

    def missing_passage(self, book: str, chapter: int, verses: Sequence[VerseRange]) -> str | None:
        """Why the passage does not exist in every translation, or None when it does."""
        counts = self._verse_counts.get(book)
        if counts is None:
            return f"livro desconhecido {book!r}; use a abreviação da Bíblia (ex.: Gn, 1Tn)"
        if not 1 <= chapter <= len(counts):
            return f"{book} tem {len(counts)} capítulos; recebido o capítulo {chapter}"
        last = max((span.end for span in verses), default=0)
        if last > counts[chapter - 1]:
            return f"{book} {chapter} tem {counts[chapter - 1]} versículos; recebido o versículo {last}"
        return None

    def book_facts(self, book: str) -> BookFacts | None:
        """Name, number in the Bible (1-based), chapter and verse counts of ``book``."""
        counts = self._verse_counts.get(book)
        if counts is None:
            return None
        return BookFacts(
            name=self._names.get(book, book),
            position=self._positions[book],
            chapters=len(counts),
            verses=sum(counts),
        )
