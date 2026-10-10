"""The delete path against the real database: race translation and distinct counts
(spec 018 FR-011, FR-014; research R-04, R-05)."""

from datetime import date, datetime, timezone

import pytest
from django.db import IntegrityError

from core.domain.exceptions import SongInUseError
from features.songs.dtos import SongUsage
from features.songs.models.setlist import Setlist, SetlistItem
from features.songs.models.song import Played, Song
from features.songs.repositories.song_repository import SongRepositoryImpl
from features.songs.services.song_service import SongService
from features.songs.tests.fakes import BlindUsageSongRepository

MAR_08 = date(2026, 3, 8)
MAR_15 = date(2026, 3, 15)
OCT_18 = date(2026, 10, 18)
OCT_25 = date(2026, 10, 25)


@pytest.fixture
def song() -> Song:
    return Song.objects.create(title="Oceans", artist="Hillsong")


def _play(song: Song, day: date, position: int = 1) -> None:
    Played.objects.create(song=song, tone="G", position=position, date=day)


def _setlist(song: Song, day: date) -> None:
    setlist = Setlist.objects.create(date=day, saved_at=datetime(2026, 10, 10, tzinfo=timezone.utc))
    SetlistItem.objects.create(setlist=setlist, position=1, song=song, tone="G")


@pytest.mark.django_db
class TestRaceTranslation:
    def test_play_saved_after_the_check_is_a_409_not_a_500(self, song: Song) -> None:
        # The service's check sees nothing; the real collector then meets PROTECT.
        _play(song, MAR_08)
        with pytest.raises(SongInUseError) as caught:
            SongService(BlindUsageSongRepository()).delete_song(song.pk)
        assert caught.value.plays == 1
        assert Song.objects.filter(pk=song.pk).exists()
        assert Played.objects.filter(song=song).count() == 1

    def test_deferred_foreign_key_failure_is_translated(self, song: Song) -> None:
        # PostgreSQL reports a late reference at commit; SQLite cannot reproduce that.
        _play(song, MAR_08)
        with pytest.raises(SongInUseError):
            with SongRepositoryImpl()._translate_in_use(song):
                raise IntegrityError("FOREIGN KEY constraint failed")

    def test_integrity_error_with_no_reference_is_re_raised(self, song: Song) -> None:
        with pytest.raises(IntegrityError):
            with SongRepositoryImpl()._translate_in_use(song):
                raise IntegrityError("something else")


@pytest.mark.django_db
def test_usage_counts_distinct_dates(song: Song) -> None:
    _play(song, MAR_08, position=1)
    _play(song, MAR_08, position=3)
    _play(song, MAR_15)
    _setlist(song, OCT_25)
    _setlist(song, OCT_18)
    assert SongRepositoryImpl().get_song_usage(song.pk) == SongUsage(
        plays=2, setlist_dates=[OCT_18, OCT_25]
    )
