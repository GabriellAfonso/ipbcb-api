"""Turning the places the app sends into canonical ``BiblePlace`` values (FR-014)."""

from collections.abc import Sequence

from core.domain.bible_exceptions import place_label
from core.domain.exceptions import BiblePlaceInvalidError
from features.bible.domain.canon import BibleCanon, BiblePlace
from features.bible.video_dtos import BiblePlaceDTO, BibleVideoPlaceDTO


def canonical_place(canon: BibleCanon, book: str, chapter: int | None) -> BiblePlace:
    """The place with its canonical book, or ``BiblePlaceInvalidError``.

    >>> canonical_place(canon, "gn", 1)
    BiblePlace(book='Gn', chapter=1)
    """
    canonical = canon.resolve(book)
    if canonical is None:
        raise BiblePlaceInvalidError(
            f"Livro desconhecido: {book!r}; use a abreviação servida pela Bíblia (ex.: 'Gn')."
        )
    if chapter is not None and not canon.has_chapter(canonical, chapter):
        raise BiblePlaceInvalidError(
            f"{canonical} não tem o capítulo {chapter}; esperado de 1 ao último capítulo do livro."
        )
    return BiblePlace(canonical, chapter)


def canonical_places(canon: BibleCanon, places: Sequence[BiblePlaceDTO]) -> list[BiblePlace]:
    """Every place canonical, in the order sent. A place repeated (even spelled another way) is
    refused: a video appears at most once per place.

    >>> canonical_places(canon, [BiblePlaceDTO(book="Gn", chapter=None)])
    [BiblePlace(book='Gn', chapter=None)]
    """
    resolved = [canonical_place(canon, place.book, place.chapter) for place in places]
    seen: set[BiblePlace] = set()
    for place in resolved:
        if place in seen:
            raise BiblePlaceInvalidError(
                f"Local repetido: {place_label(place.book, place.chapter)}; "
                "cada local pode aparecer uma vez."
            )
        seen.add(place)
    return resolved


def sorted_places(
    canon: BibleCanon, places: Sequence[BibleVideoPlaceDTO]
) -> list[BibleVideoPlaceDTO]:
    """Canonical book order, the whole book first, then chapter."""
    return sorted(places, key=lambda p: canon.place_sort_key(BiblePlace(p.book, p.chapter)))
