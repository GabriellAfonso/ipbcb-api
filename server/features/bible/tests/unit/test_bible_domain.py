"""Pure rules of feature 025: the canon, YouTube links and last-write-wins."""

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from features.bible.domain.canon import BibleCanon, BiblePlace
from features.bible.dtos import BibleBook
from features.bible.repositories.bible_text import BibleRepositoryImpl, shared_verse_counts
from features.bible.domain.last_write_wins import winning_changes
from features.bible.domain.youtube_links import (
    YouTubeKind,
    YouTubeTarget,
    parse_youtube_link,
    video_thumbnail_url,
)
from features.bible.tests.fakes import SMALL_CANON

VIDEO_ID = "dQw4w9WgXcQ"
PLAYLIST_ID = "PLx0sYbCqOb8TBPRdmBHs5Iftvv9TPboYG"


class TestBibleCanon:
    def test_resolve_ignores_case_but_not_accents(self) -> None:
        assert SMALL_CANON.resolve("gn") == "Gn"
        assert SMALL_CANON.resolve("JÓ") == "Jó"
        assert SMALL_CANON.resolve("jo") == "Jo"
        assert SMALL_CANON.resolve("Xy") is None

    @pytest.mark.parametrize(
        ("chapter", "expected"), [(0, False), (1, True), (50, True), (51, False)]
    )
    def test_has_chapter_is_one_based_up_to_the_count(self, chapter: int, expected: bool) -> None:
        assert SMALL_CANON.has_chapter("Gn", chapter) is expected

    def test_unknown_book_has_no_chapter(self) -> None:
        assert SMALL_CANON.has_chapter("Xy", 1) is False

    def test_place_sort_key_puts_whole_book_first_then_chapters_in_book_order(self) -> None:
        places = [BiblePlace("Êx", 1), BiblePlace("Gn", 2), BiblePlace("Gn", None)]
        ordered = sorted(places, key=SMALL_CANON.place_sort_key)
        assert ordered == [BiblePlace("Gn", None), BiblePlace("Gn", 2), BiblePlace("Êx", 1)]

    def test_books_keep_canonical_order(self) -> None:
        assert SMALL_CANON.books == ["Gn", "Êx", "Jo", "Jó", "Sl"]

    def test_identifiers_differing_only_in_case_are_refused(self) -> None:
        with pytest.raises(ValueError, match="differ only in case"):
            BibleCanon({"Gn": 50, "GN": 1})


class TestParseYouTubeLink:
    @pytest.mark.parametrize(
        "link",
        [
            f"https://www.youtube.com/watch?v={VIDEO_ID}",
            f"http://youtube.com/watch?v={VIDEO_ID}&feature=share",
            f"https://m.youtube.com/watch?v={VIDEO_ID}",
            f"https://music.youtube.com/watch?v={VIDEO_ID}",
            f"https://youtu.be/{VIDEO_ID}",
            f"youtu.be/{VIDEO_ID}",
            f"https://www.youtube.com/shorts/{VIDEO_ID}",
            f"https://www.youtube.com/live/{VIDEO_ID}?si=abc",
            f"https://www.youtube.com/watch?v={VIDEO_ID}&list={PLAYLIST_ID}",
            f"  https://YOUTUBE.com/watch?v={VIDEO_ID}  ",
        ],
    )
    def test_video_links(self, link: str) -> None:
        assert parse_youtube_link(link) == YouTubeTarget(YouTubeKind.VIDEO, VIDEO_ID)

    def test_playlist_link(self) -> None:
        target = parse_youtube_link(f"https://www.youtube.com/playlist?list={PLAYLIST_ID}")
        assert target == YouTubeTarget(YouTubeKind.PLAYLIST, PLAYLIST_ID)
        assert target.url == f"https://www.youtube.com/playlist?list={PLAYLIST_ID}"

    @pytest.mark.parametrize(
        ("query", "seconds"),
        [("t=90", 90), ("t=90s", 90), ("t=1m30s", 90), ("t=1h2m3s", 3723), ("start=15", 15)],
    )
    def test_start_time_is_kept_in_seconds(self, query: str, seconds: int) -> None:
        target = parse_youtube_link(f"https://youtu.be/{VIDEO_ID}?{query}")
        assert target is not None
        assert target.start_seconds == seconds
        assert target.url == f"https://www.youtube.com/watch?v={VIDEO_ID}&t={seconds}"

    @pytest.mark.parametrize("query", ["t=0", "t=abc", "t="])
    def test_unreadable_or_zero_start_is_dropped(self, query: str) -> None:
        target = parse_youtube_link(f"https://youtu.be/{VIDEO_ID}?{query}")
        assert target == YouTubeTarget(YouTubeKind.VIDEO, VIDEO_ID)
        assert target.url == f"https://www.youtube.com/watch?v={VIDEO_ID}"

    @pytest.mark.parametrize(
        "link",
        [
            "",
            "not a link",
            f"https://vimeo.com/{VIDEO_ID}",
            f"https://youtube.com.evil.test/watch?v={VIDEO_ID}",
            f"ftp://youtube.com/watch?v={VIDEO_ID}",
            "https://www.youtube.com/watch?v=short",
            "https://www.youtube.com/watch",
            "https://www.youtube.com/channel/UC123",
            "https://www.youtube.com/playlist?list=bad id",
            f"https://youtu.be/{VIDEO_ID}/extra",
        ],
    )
    def test_anything_else_is_refused(self, link: str) -> None:
        assert parse_youtube_link(link) is None

    def test_video_thumbnail_needs_no_lookup(self) -> None:
        assert video_thumbnail_url(VIDEO_ID) == f"https://i.ytimg.com/vi/{VIDEO_ID}/hqdefault.jpg"


@dataclass(frozen=True)
class _Change:
    changed_at: datetime
    label: str = ""


def _at(minute: int) -> datetime:
    return datetime(2026, 10, 27, 13, minute, tzinfo=UTC)


class TestWinningChanges:
    def test_nothing_stored_wins(self) -> None:
        change = _Change(_at(0))
        assert winning_changes({}, [("Gn 1", change)]) == [change]

    def test_older_than_stored_loses(self) -> None:
        assert winning_changes({"Gn 1": _at(5)}, [("Gn 1", _Change(_at(0)))]) == []

    def test_equal_to_stored_loses_so_a_replay_is_a_no_op(self) -> None:
        assert winning_changes({"Gn 1": _at(5)}, [("Gn 1", _Change(_at(5)))]) == []

    def test_newer_than_stored_wins(self) -> None:
        change = _Change(_at(6))
        assert winning_changes({"Gn 1": _at(5)}, [("Gn 1", change)]) == [change]

    def test_same_target_twice_keeps_the_newest_whatever_the_order(self) -> None:
        newer, older = _Change(_at(9), "newer"), _Change(_at(3), "older")
        assert winning_changes({}, [("Gn 1", newer), ("Gn 1", older)]) == [newer]
        assert winning_changes({}, [("Gn 1", older), ("Gn 1", newer)]) == [newer]

    def test_targets_are_independent(self) -> None:
        a, b = _Change(_at(1), "a"), _Change(_at(1), "b")
        assert winning_changes({"Gn 1": _at(2)}, [("Gn 1", a), ("Gn 2", b)]) == [b]


class TestSharedVerseCounts:
    def test_keeps_the_fewest_verses_of_each_chapter(self) -> None:
        naa = [_book("Gn", [3, 5]), _book("Ap", [4])]
        ara = [_book("Gn", [3, 4]), _book("Ap", [6])]

        assert shared_verse_counts({"NAA": naa, "ARA": ara}) == {"Gn": [3, 4], "Ap": [4]}

    def test_no_translation_gives_no_books(self) -> None:
        assert shared_verse_counts({}) == {}


class TestBibleRepositoryOutline:
    def test_real_data_counts_and_names(self) -> None:
        repository = BibleRepositoryImpl()

        counts = repository.verse_counts_by_book()
        names = repository.book_names()

        assert len(counts) == 66
        assert list(counts)[40] == "Mc"
        assert len(counts["Mc"]) == 16
        assert names["Mc"] == "Marcos"


def _book(abbrev: str, verse_counts: list[int]) -> BibleBook:
    return BibleBook(abbrev=abbrev, name=abbrev, chapters=[["v"] * count for count in verse_counts])
