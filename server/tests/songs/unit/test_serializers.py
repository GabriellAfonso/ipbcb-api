import pytest
from datetime import date

from features.songs.models import Song, Played, ChordChart, Lyrics
from features.songs.serializers.serializers import (
    SongSerializer,
    PlayedSerializer,
    ChordChartSerializer,
    LyricsSerializer,
)


@pytest.mark.django_db
class TestSongSerializer:
    def test_fields(self) -> None:
        song = Song.objects.create(title="Grace", artist="Artist")
        data = SongSerializer(song).data
        assert set(data.keys()) == {"id", "title", "artist"}
        assert data["title"] == "Grace"


@pytest.mark.django_db
class TestPlayedSerializer:
    def test_nested_song_and_date_format(self) -> None:
        song = Song.objects.create(title="Holy", artist="Band")
        played = Played.objects.create(song=song, tone="G", position=1, date=date(2026, 3, 15))
        data = PlayedSerializer(played).data

        assert data["date"] == "15/03/2026"
        assert data["song"]["title"] == "Holy"
        assert data["song"]["artist"] == "Band"
        assert set(data.keys()) == {"id", "song", "date", "tone", "position"}

    def test_fields_with_none_song(self) -> None:
        played = Played.objects.create(song=None, tone="C", position=2, date=date(2026, 1, 1))
        data = PlayedSerializer(played).data
        assert data["song"] is None


@pytest.mark.django_db
class TestChordChartSerializer:
    def test_fields(self) -> None:
        song = Song.objects.create(title="Oceans", artist="Hillsong")
        chart = ChordChart.objects.create(
            song=song, content="Am G C", tone="Am", instrument="Guitar"
        )
        data = ChordChartSerializer(chart).data
        assert set(data.keys()) == {"id", "song_id", "content", "tone", "instrument", "updated_at"}
        assert data["song_id"] == song.id


@pytest.mark.django_db
class TestLyricsSerializer:
    def test_fields(self) -> None:
        song = Song.objects.create(title="Grace", artist="Artist")
        lyrics = Lyrics.objects.create(song=song, content="Amazing grace how sweet")
        data = LyricsSerializer(lyrics).data
        assert set(data.keys()) == {"id", "song_id", "content", "updated_at"}
        assert data["content"] == "Amazing grace how sweet"
