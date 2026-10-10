from datetime import date

import pytest

from core.domain.exceptions import SongInUseError, SongNotFoundError
from features.songs.dtos import SongUsage
from features.songs.models.song import Song
from features.songs.services.song_service import SongService
from features.songs.tests.fakes import FakeSongRepository

OCT_18 = date(2026, 10, 18)


def _repo(usage: SongUsage | None = None) -> FakeSongRepository:
    song = Song(id=42, title="Oceans", artist="Hillsong")
    return FakeSongRepository({42: song}, usage={42: usage} if usage else None)


def test_free_song_is_deleted() -> None:
    repo = _repo()
    SongService(repo).delete_song(42)
    assert 42 not in repo.songs
    assert repo.calls == ["get_song_usage", "delete_song"]


def test_unknown_id() -> None:
    repo = _repo()
    with pytest.raises(SongNotFoundError):
        SongService(repo).delete_song(7)
    assert repo.calls == []


@pytest.mark.parametrize(
    ("usage", "reasons"),
    [
        (SongUsage(plays=7, setlist_dates=[]), "foi tocada em 7 domingos"),
        (SongUsage(plays=0, setlist_dates=[OCT_18]), "está na setlist de 18/10/2026"),
        (
            SongUsage(plays=7, setlist_dates=[OCT_18]),
            "foi tocada em 7 domingos e está na setlist de 18/10/2026",
        ),
    ],
    ids=["plays-only", "setlist-only", "both"],
)
def test_song_in_use_is_refused(usage: SongUsage, reasons: str) -> None:
    repo = _repo(usage)
    with pytest.raises(SongInUseError) as caught:
        SongService(repo).delete_song(42)
    assert str(caught.value) == f'A música "Oceans" não pode ser excluída: {reasons}.'
    assert caught.value.extra_context() == {
        "song_id": 42,
        "title": "Oceans",
        "plays": usage.plays,
        "setlist_dates": [d.isoformat() for d in usage.setlist_dates],
    }
    assert "delete_song" not in repo.calls
    assert 42 in repo.songs
