import json
from pathlib import Path

import pytest

from features.doctrine.dtos import BibleReference, VerseSpan
from features.doctrine.tests.bible_verse_index import BIBLE_DATA_FILES, BibleVerseIndex


def _write_bible(tmp_path: Path, name: str, books: list[dict[str, object]]) -> Path:
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(books, ensure_ascii=False), encoding="utf-8")
    return path


def _reference(book: str, chapter: int, *verses: tuple[int, int]) -> BibleReference:
    spans = [VerseSpan(start=start, end=end) for start, end in verses]
    return BibleReference(book=book, chapter=chapter, verses=spans)


@pytest.fixture
def index(tmp_path: Path) -> BibleVerseIndex:
    # "Rm" 1 has 3 verses in A and 2 in B; "Sl" 2 exists only in A; a multi-paragraph verse
    # (a list) counts as one verse.
    version_a = _write_bible(
        tmp_path,
        "A",
        [
            {"abbrev": "Rm", "name": "Romanos", "chapters": [["v1", "v2", "v3"]]},
            {"abbrev": "Sl", "name": "Salmos", "chapters": [["v1"], ["v1"]]},
        ],
    )
    version_b = _write_bible(
        tmp_path,
        "B",
        [
            {"abbrev": "Rm", "name": "Romanos", "chapters": [["v1", ["v2a", "v2b"]]]},
            {"abbrev": "Sl", "name": "Salmos", "chapters": [["v1"]]},
        ],
    )
    return BibleVerseIndex.from_files([version_a, version_b])


class TestBibleVerseIndex:
    def test_verse_present_in_every_version_exists(self, index: BibleVerseIndex) -> None:
        assert index.missing_verses(_reference("Rm", 1, (1, 2))) is None

    def test_uses_the_minimum_verse_count(self, index: BibleVerseIndex) -> None:
        reason = index.missing_verses(_reference("Rm", 1, (3, 3)))
        assert reason == "Rm 1 has 2 verses in every version; got verse 3"

    def test_chapter_missing_in_one_version_does_not_exist(self, index: BibleVerseIndex) -> None:
        reason = index.missing_verses(_reference("Sl", 2))
        assert reason == "Sl 2 is not a chapter in every version"

    def test_whole_chapter_only_needs_the_chapter(self, index: BibleVerseIndex) -> None:
        assert index.missing_verses(_reference("Sl", 1)) is None

    def test_real_bible_files_use_1tn_for_1_timothy(self) -> None:
        # Clarification Q2: the Bible domain serves "1Tn", and doctrine references follow it.
        real_index = BibleVerseIndex.from_files(BIBLE_DATA_FILES)
        assert real_index.has_book("1Tn")
        assert not real_index.has_book("1Tm")

    def test_unknown_book(self, index: BibleVerseIndex) -> None:
        assert not index.has_book("1Tm")
        assert index.has_book("Rm")
        assert index.missing_verses(_reference("1Tm", 1)) is not None
