import pytest
from pydantic import ValidationError

from features.bible.dtos import BibleBook, BibleHeading


def _book(headings: list[list[BibleHeading]]) -> BibleBook:
    return BibleBook(
        abbrev="Gn",
        name="Gênesis",
        chapters=[["v1", "v2"], ["v1"]],
        headings=headings,
    )


class TestBibleBookHeadings:
    def test_defaults_to_empty_when_absent(self) -> None:
        book = BibleBook(abbrev="Gn", name="Gênesis", chapters=[["v1"]])
        assert book.headings == []

    def test_accepts_headings_parallel_to_chapters(self) -> None:
        heading = BibleHeading(verse=2, level=1, title="A criação do Universo")
        book = _book([[heading], []])
        assert book.headings[0][0].verse == 2

    def test_rejects_chapter_count_mismatch(self) -> None:
        with pytest.raises(ValidationError, match="expected 2"):
            _book([[]])

    def test_rejects_verse_beyond_chapter(self) -> None:
        heading = BibleHeading(verse=2, level=1, title="Fora")
        with pytest.raises(ValidationError, match="expected 1..1"):
            _book([[], [heading]])


class TestBibleHeading:
    @pytest.mark.parametrize("level", [0, 4])
    def test_rejects_level_out_of_range(self, level: int) -> None:
        with pytest.raises(ValidationError):
            BibleHeading(verse=1, level=level, title="X")

    def test_rejects_verse_zero(self) -> None:
        with pytest.raises(ValidationError):
            BibleHeading(verse=0, level=1, title="X")
