import pytest
from datetime import date, timedelta

from django.utils.timezone import now
from rest_framework.test import APIClient

from features.songs.models import Song, Played
from features.songs.repositories.song_repository import SongRepositoryImpl


URL = "/api/suggested-songs/"


def _old_date() -> date:
    """Date older than 90 days."""
    return (now() - timedelta(days=120)).date()


def _recent_date() -> date:
    """Date within last 90 days."""
    return (now() - timedelta(days=30)).date()


def _create_old_plays() -> list[Played]:
    """Create songs played >90 days ago at positions 1-4."""
    plays = []
    for pos in range(1, 5):
        song = Song.objects.create(title=f"Old Song {pos}", artist=f"Artist {pos}")
        played = Played.objects.create(song=song, tone="G", position=pos, date=_old_date())
        plays.append(played)
    return plays


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.mark.django_db
class TestSuggestedSongsAPI:
    def test_returns_suggestions_for_all_positions(self, client: APIClient) -> None:
        _create_old_plays()
        resp = client.get(URL)
        assert resp.status_code == 200
        positions = {s["position"] for s in resp.data}
        assert positions == {1, 2, 3, 4}

    def test_excludes_recently_played_songs(self, client: APIClient) -> None:
        old_plays = _create_old_plays()
        # Mark one old song as recently played too
        Played.objects.create(song=old_plays[0].song, tone="C", position=1, date=_recent_date())
        resp = client.get(URL)
        assert resp.status_code == 200
        suggested_song_titles = {s["song"]["title"] for s in resp.data if s.get("song")}
        assert old_plays[0].song is not None
        assert old_plays[0].song.title not in suggested_song_titles

    def test_no_duplicate_songs(self, client: APIClient) -> None:
        _create_old_plays()
        resp = client.get(URL)
        assert resp.status_code == 200
        song_ids = [s["song"]["id"] for s in resp.data if s.get("song")]
        assert len(song_ids) == len(set(song_ids))

    def test_with_fixed_param(self, client: APIClient) -> None:
        old_plays = _create_old_plays()
        fixed_id = old_plays[0].id
        resp = client.get(URL, {"fixed": f"1:{fixed_id}"})
        assert resp.status_code == 200
        pos1 = next((s for s in resp.data if s["position"] == 1), None)
        assert pos1 is not None
        assert pos1["id"] == fixed_id

    def test_returns_empty_when_no_eligible_songs(self, client: APIClient) -> None:
        resp = client.get(URL)
        assert resp.status_code == 200
        assert resp.data == []

    def test_results_sorted_by_position(self, client: APIClient) -> None:
        _create_old_plays()
        resp = client.get(URL)
        assert resp.status_code == 200
        positions = [s["position"] for s in resp.data]
        assert positions == sorted(positions)

    def test_exclude_skips_the_song_in_its_position(self, client: APIClient) -> None:
        plays = _create_old_plays()
        other = Song.objects.create(title="Other", artist="Artist")
        Played.objects.create(song=other, tone="A", position=3, date=_old_date())
        resp = client.get(URL, {"exclude": f"3:{plays[2].song_id},1:{other.pk}"})
        assert resp.status_code == 200
        by_position = {s["position"]: s["song"]["id"] for s in resp.data}
        assert by_position == {
            1: plays[0].song_id,
            2: plays[1].song_id,
            3: other.pk,
            4: plays[3].song_id,
        }

    def test_exhausted_exclude_falls_back_to_the_full_pool(self, client: APIClient) -> None:
        plays = _create_old_plays()
        resp = client.get(URL, {"exclude": f"3:{plays[2].song_id}"})
        assert resp.status_code == 200
        pos3 = next(s for s in resp.data if s["position"] == 3)
        assert pos3["id"] == plays[2].id


@pytest.mark.django_db
class TestSuggestionQueries:
    def test_candidates_hold_each_song_once(self) -> None:
        busy = Song.objects.create(title="Busy", artist="A")
        rare = Song.objects.create(title="Rare", artist="A")
        for _ in range(12):
            Played.objects.create(song=busy, tone="G", position=3, date=_old_date())
        Played.objects.create(song=rare, tone="G", position=3, date=_old_date())
        Played.objects.create(song=None, tone="G", position=3, date=_old_date())
        cutoff = (now() - timedelta(days=90)).date()

        candidates = SongRepositoryImpl().get_candidate_song_ids(3, cutoff, set())

        assert candidates == sorted([busy.pk, rare.pk])

    def test_candidates_drop_excluded_and_recent_plays(self) -> None:
        recent, excluded, kept, other = (p.song for p in _create_old_plays())
        assert recent and excluded and kept and other
        Played.objects.create(song=recent, tone="G", position=3, date=_recent_date())
        Played.objects.create(song=excluded, tone="G", position=3, date=_old_date())
        Played.objects.create(song=other, tone="G", position=3, date=_old_date())
        cutoff = (now() - timedelta(days=90)).date()

        candidates = SongRepositoryImpl().get_candidate_song_ids(3, cutoff, {excluded.pk})

        # The recent play is after the cutoff; the service blocks that song separately.
        assert candidates == sorted([kept.pk, other.pk])

    def test_latest_play_is_the_newest_in_that_position(self) -> None:
        song = Song.objects.create(title="Song", artist="A")
        Played.objects.create(
            song=song, tone="C", position=3, date=_old_date() - timedelta(days=60)
        )
        latest = Played.objects.create(song=song, tone="D", position=3, date=_old_date())
        Played.objects.create(song=song, tone="E", position=1, date=_recent_date())

        assert SongRepositoryImpl().get_latest_play(song.pk, 3) == latest
