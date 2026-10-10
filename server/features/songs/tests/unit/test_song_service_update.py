import pytest

from core.domain.exceptions import DuplicateSongError, SongNotFoundError
from features.songs.dtos import SongChangesInput
from features.songs.models.song import Song
from features.songs.services.song_service import SongService
from features.songs.tests.fakes import FakeSongRepository

LINK = "https://youtu.be/old"


def _catalogue(*extra: Song) -> FakeSongRepository:
    oceans = Song(id=1, title="oceans", artist="Hillsong", youtube_link=LINK)
    return FakeSongRepository({song.pk: song for song in (oceans, *extra)})


def _edit(repo: FakeSongRepository, song_id: int, **changes: str) -> Song:
    return SongService(repo).update_song(song_id, SongChangesInput.model_validate(changes))


class TestEditFields:
    def test_title_alone(self) -> None:
        song = _edit(_catalogue(), 1, title="Oceans (Where Feet May Fail)")
        assert (song.title, song.artist, song.youtube_link) == (
            "Oceans (Where Feet May Fail)",
            "Hillsong",
            LINK,
        )

    def test_artist_alone(self) -> None:
        song = _edit(_catalogue(), 1, artist="Hillsong United")
        assert (song.title, song.artist, song.youtube_link) == ("oceans", "Hillsong United", LINK)

    def test_link_alone(self) -> None:
        song = _edit(_catalogue(), 1, youtube_link="https://youtu.be/new")
        assert (song.title, song.artist, song.youtube_link) == (
            "oceans",
            "Hillsong",
            "https://youtu.be/new",
        )

    def test_empty_link_clears_it(self) -> None:
        assert _edit(_catalogue(), 1, youtube_link="").youtube_link == ""


class TestDuplicateRule:
    def test_renaming_onto_another_song_conflicts(self) -> None:
        repo = _catalogue(Song(id=2, title="Way Maker", artist="Sinach"))
        with pytest.raises(DuplicateSongError) as caught:
            _edit(repo, 2, title=" OCEANS ", artist="hillsong")
        assert caught.value.extra_context() == {"title": "OCEANS", "artist": "hillsong"}
        assert "update_song" not in repo.calls
        assert repo.songs[2].title == "Way Maker"

    @pytest.mark.parametrize("title", ["oceans", "Oceans", " OCEANS "])
    def test_same_pair_any_case_never_queries(self, title: str) -> None:
        repo = _catalogue()
        assert _edit(repo, 1, title=title).title == title.strip()
        assert "song_exists" not in repo.calls

    def test_link_edit_on_a_legacy_duplicate_is_allowed(self) -> None:
        repo = _catalogue(Song(id=2, title="Oceans", artist="hillsong"))
        assert _edit(repo, 2, youtube_link="https://youtu.be/fix").youtube_link.endswith("fix")
        assert "song_exists" not in repo.calls

    def test_new_free_pair_checks_and_saves(self) -> None:
        repo = _catalogue()
        _edit(repo, 1, title="Way Maker")
        assert repo.calls == ["song_exists", "update_song"]


def test_unknown_id() -> None:
    with pytest.raises(SongNotFoundError):
        _edit(_catalogue(), 99, title="X")
