import pytest
from pydantic import ValidationError as PydanticValidationError

from features.songs.dtos import NewSongInput


class TestNewSongInput:
    def test_strips_title_artist_and_link(self) -> None:
        song = NewSongInput(
            title=" Oceans ", artist=" Hillsong ", youtube_link=" https://youtu.be/x "
        )
        assert (song.title, song.artist, song.youtube_link) == (
            "Oceans",
            "Hillsong",
            "https://youtu.be/x",
        )

    def test_youtube_link_defaults_to_empty(self) -> None:
        assert NewSongInput(title="Oceans", artist="Hillsong").youtube_link == ""

    def test_keeps_link_as_typed(self) -> None:
        # HttpUrl would append a trailing slash; the stored value must be what the user sent.
        song = NewSongInput(title="Oceans", artist="Hillsong", youtube_link="https://youtube.com")
        assert song.youtube_link == "https://youtube.com"

    def test_accepts_100_characters_after_trim(self) -> None:
        song = NewSongInput(title=" " + "x" * 100 + " ", artist="Hillsong")
        assert len(song.title) == 100

    @pytest.mark.parametrize(
        "fields",
        [
            {"title": "", "artist": "Hillsong"},
            {"title": "Oceans", "artist": "  "},
            {"title": "x" * 101, "artist": "Hillsong"},
            {"title": "Oceans", "artist": "Hillsong", "youtube_link": "ftp://x"},
            {"title": "Oceans", "artist": "Hillsong", "youtube_link": "https://x/" + "a" * 200},
            {"title": "Oceans", "artist": "Hillsong", "category": "Worship"},
        ],
    )
    def test_rejects_invalid_fields(self, fields: dict[str, str]) -> None:
        with pytest.raises(PydanticValidationError):
            NewSongInput.model_validate(fields)
