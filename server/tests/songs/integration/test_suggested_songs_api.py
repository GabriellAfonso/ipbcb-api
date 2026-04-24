import pytest
from datetime import date, timedelta

from django.utils.timezone import now
from rest_framework.test import APIClient

from features.songs.models import Song, Played


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
