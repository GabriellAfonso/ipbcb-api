import pytest

from core.domain.exceptions import BibleVersionNotFound
from features.bible.domain.canon import BibleCanon
from features.bible.dtos import BibleBook
from features.bible.services import BibleService


SAMPLE_BOOKS = [
    BibleBook(abbrev="Gn", name="Gênesis", chapters=[["No princípio..."]]),
]


class FakeBibleRepository:
    """Named fake for BibleRepository."""

    def __init__(self) -> None:
        self._bibles: dict[str, list[BibleBook]] = {
            "arc": SAMPLE_BOOKS,
            "nvi": SAMPLE_BOOKS,
        }

    def list_versions(self) -> list[str]:
        return sorted(self._bibles.keys())

    def get_version(self, name: str) -> list[BibleBook] | None:
        return self._bibles.get(name)

    def canon(self) -> BibleCanon:
        return BibleCanon({"Gn": 1})


class TestBibleServiceListVersions:
    def test_returns_sorted_versions(self) -> None:
        service = BibleService(bible_repository=FakeBibleRepository())
        assert service.list_versions() == ["arc", "nvi"]


class TestBibleServiceGetVersion:
    def test_returns_books_for_existing_version(self) -> None:
        service = BibleService(bible_repository=FakeBibleRepository())
        books = service.get_version("nvi")
        assert len(books) == 1
        assert books[0].abbrev == "Gn"

    def test_raises_not_found_for_unknown_version(self) -> None:
        service = BibleService(bible_repository=FakeBibleRepository())
        with pytest.raises(BibleVersionNotFound, match="unknown"):
            service.get_version("unknown")
