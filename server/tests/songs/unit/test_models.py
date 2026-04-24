import pytest
from datetime import date

from features.songs.models import Category, Song, Played, Lyrics, ChordChart, Hymn


@pytest.mark.django_db
class TestCategoryStr:
    def test_returns_name(self) -> None:
        cat = Category.objects.create(name="Adoração")
        assert str(cat) == "Adoração"


@pytest.mark.django_db
class TestSongStr:
    def test_returns_title_and_artist(self) -> None:
        song = Song.objects.create(title="Amazing Grace", artist="John Newton")
        assert str(song) == "Amazing Grace ------- John Newton"


@pytest.mark.django_db
class TestPlayedStr:
    def test_returns_title_and_date(self) -> None:
        song = Song.objects.create(title="Holy Holy", artist="Artist")
        played = Played.objects.create(song=song, tone="G", position=1, date=date(2026, 3, 15))
        assert str(played) == "Holy Holy ------- 15/03/2026"

    def test_returns_question_mark_when_song_is_none(self) -> None:
        played = Played.objects.create(song=None, tone="C", position=1, date=date(2026, 1, 1))
        assert str(played) == "? ------- 01/01/2026"


@pytest.mark.django_db
class TestLyricsStr:
    def test_returns_lyrics_prefix_and_song_title(self) -> None:
        song = Song.objects.create(title="Grace", artist="Artist")
        lyrics = Lyrics.objects.create(song=song, content="Some lyrics")
        assert str(lyrics) == "Lyrics — Grace"


@pytest.mark.django_db
class TestChordChartStr:
    def test_with_tone_and_instrument(self) -> None:
        song = Song.objects.create(title="Oceans", artist="Hillsong")
        chart = ChordChart.objects.create(song=song, content="...", tone="G", instrument="Guitar")
        assert str(chart) == "Chord Chart — Oceans | G | Guitar"

    def test_with_tone_only(self) -> None:
        song = Song.objects.create(title="Oceans", artist="Hillsong")
        chart = ChordChart.objects.create(song=song, content="...", tone="D", instrument="")
        assert str(chart) == "Chord Chart — Oceans | D"

    def test_without_tone_and_instrument(self) -> None:
        song = Song.objects.create(title="Oceans", artist="Hillsong")
        chart = ChordChart.objects.create(song=song, content="...", tone="", instrument="")
        assert str(chart) == "Chord Chart — Oceans"


@pytest.mark.django_db
class TestHymnStr:
    def test_returns_number_and_title(self) -> None:
        hymn = Hymn.objects.create(number="110", title="Santo Santo", lyrics={"verses": []})
        assert str(hymn) == "110 - Santo Santo"
