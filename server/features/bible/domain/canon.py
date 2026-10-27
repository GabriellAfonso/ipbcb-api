"""The 66 books, their order and chapter counts — the catalogue videos and progress point into.

Pure: built from the loaded translations by the repository (specs/025-bible-videos R-02). A book
is identified by the ``abbrev`` the Bible endpoints serve (``Gn``, ``Êx``, ``1Tn``); input is
matched ignoring case but never ignoring accents, so ``Jo`` (João) and ``Jó`` stay apart.
"""

from collections.abc import Mapping, Sequence
from typing import NamedTuple


class BiblePlace(NamedTuple):
    """Where a video appears: one chapter of a book, or the whole book (``chapter`` None)."""

    book: str
    chapter: int | None


class BibleCanon:
    """Books in canonical order with their chapter counts.

    >>> canon = BibleCanon({"Gn": 50, "Êx": 40})
    >>> canon.resolve("gn"), canon.has_chapter("Gn", 51)
    ('Gn', False)
    """

    def __init__(self, chapter_counts: Mapping[str, int]) -> None:
        self._counts = dict(chapter_counts)
        self._order = {book: index for index, book in enumerate(self._counts)}
        self._by_folded = _folded_index(list(self._counts))

    @property
    def books(self) -> list[str]:
        return list(self._counts)

    def resolve(self, book: str) -> str | None:
        """The canonical identifier ``book`` names, ignoring case, or None."""
        return self._by_folded.get(book.casefold())

    def has_chapter(self, book: str, chapter: int) -> bool:
        """Whether canonical ``book`` has chapter ``chapter`` (1-based)."""
        return 1 <= chapter <= self._counts.get(book, 0)

    def place_sort_key(self, place: BiblePlace) -> tuple[int, int]:
        """Canonical book order, the whole book before its chapters."""
        return self._order.get(place.book, len(self._order)), place.chapter or 0


def _folded_index(books: Sequence[str]) -> dict[str, str]:
    index: dict[str, str] = {}
    for book in books:
        folded = book.casefold()
        if folded in index:
            raise ValueError(
                f"Book identifiers {index[folded]!r} and {book!r} differ only in case; "
                "expected identifiers unique ignoring case."
            )
        index[folded] = book
    return index
