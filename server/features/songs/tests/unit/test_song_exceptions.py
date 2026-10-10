from datetime import date

import pytest

from core.domain.exceptions import SongInUseError, SongNotFoundError

OCT_18 = date(2026, 10, 18)
OCT_25 = date(2026, 10, 25)
NOV_01 = date(2026, 11, 1)


class TestSongNotFoundError:
    def test_is_a_not_found_naming_the_id(self) -> None:
        exc = SongNotFoundError(7)
        assert exc.error_code == "NOT_FOUND"
        assert str(exc) == "Song not found: id=7"
        assert exc.extra_context() == {"song_id": 7}


class TestSongInUseError:
    """One case per row of the wording table in contracts/song-detail-api.md."""

    @pytest.mark.parametrize(
        ("plays", "dates", "reasons"),
        [
            (1, [], "foi tocada em 1 domingo"),
            (7, [], "foi tocada em 7 domingos"),
            (0, [OCT_18], "está na setlist de 18/10/2026"),
            (0, [OCT_18, OCT_25], "está nas setlists de 18/10/2026 e 25/10/2026"),
            (
                0,
                [OCT_18, OCT_25, NOV_01],
                "está nas setlists de 18/10/2026, 25/10/2026 e 01/11/2026",
            ),
            (7, [OCT_18], "foi tocada em 7 domingos e está na setlist de 18/10/2026"),
        ],
    )
    def test_message_names_only_the_reasons_that_apply(
        self, plays: int, dates: list[date], reasons: str
    ) -> None:
        exc = SongInUseError(42, "Oceans", plays, dates)
        assert str(exc) == f'A música "Oceans" não pode ser excluída: {reasons}.'

    def test_is_a_conflict_with_iso_dates(self) -> None:
        exc = SongInUseError(42, "Oceans", 7, [OCT_18])
        assert exc.error_code == "CONFLICT"
        assert exc.extra_context() == {
            "song_id": 42,
            "title": "Oceans",
            "plays": 7,
            "setlist_dates": ["2026-10-18"],
        }
