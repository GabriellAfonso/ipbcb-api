import pytest
from rest_framework.test import APIClient

from features.songs.models import Song
from tests.conftest import make_admin_client, make_auth_client, make_user


URL = "/api/played/register/"


def _make_songs(n: int = 2) -> list[Song]:
    return [Song.objects.create(title=f"Song {i}", artist=f"Artist {i}") for i in range(1, n + 1)]


@pytest.mark.django_db
class TestRegisterSundayPlaysAuth:
    def test_unauthenticated_returns_401(self) -> None:
        resp = APIClient().post(URL, {}, format="json")
        assert resp.status_code == 401

    def test_non_admin_returns_403(self) -> None:
        user = make_user()
        client = make_auth_client(user)
        resp = client.post(URL, {"date": "2026-03-15", "plays": []}, format="json")
        assert resp.status_code == 403


@pytest.mark.django_db
class TestRegisterSundayPlaysValidation:
    def setup_method(self) -> None:
        self.client, self.user = make_admin_client()

    def test_missing_date(self) -> None:
        resp = self.client.post(
            URL, {"plays": [{"song_id": 1, "position": 1, "tone": "G"}]}, format="json"
        )
        assert resp.status_code == 400
        assert "date" in resp.data["detail"].lower()

    def test_empty_plays(self) -> None:
        resp = self.client.post(URL, {"date": "2026-03-15", "plays": []}, format="json")
        assert resp.status_code == 400

    def test_plays_not_a_list(self) -> None:
        resp = self.client.post(URL, {"date": "2026-03-15", "plays": "not_list"}, format="json")
        assert resp.status_code == 400

    def test_invalid_date_format(self) -> None:
        songs = _make_songs(1)
        resp = self.client.post(
            URL,
            {"date": "15/03/2026", "plays": [{"song_id": songs[0].id, "position": 1, "tone": "G"}]},
            format="json",
        )
        assert resp.status_code == 400
        assert "date format" in resp.data["detail"].lower()

    def test_play_item_not_dict(self) -> None:
        resp = self.client.post(URL, {"date": "2026-03-15", "plays": ["invalid"]}, format="json")
        assert resp.status_code == 400
        assert "plays[0]" in resp.data["detail"]

    def test_missing_song_id_or_position(self) -> None:
        resp = self.client.post(
            URL, {"date": "2026-03-15", "plays": [{"tone": "G"}]}, format="json"
        )
        assert resp.status_code == 400

    def test_position_out_of_range(self) -> None:
        songs = _make_songs(1)
        resp = self.client.post(
            URL,
            {
                "date": "2026-03-15",
                "plays": [{"song_id": songs[0].id, "position": 11, "tone": "G"}],
            },
            format="json",
        )
        assert resp.status_code == 400
        assert "position" in resp.data["detail"].lower()

    def test_nonexistent_song_id(self) -> None:
        resp = self.client.post(
            URL,
            {"date": "2026-03-15", "plays": [{"song_id": 99999, "position": 1, "tone": "G"}]},
            format="json",
        )
        assert resp.status_code == 400
        assert "not found" in resp.data["detail"].lower()


@pytest.mark.django_db
class TestRegisterSundayPlaysSuccess:
    def test_creates_played_records(self) -> None:
        client, _ = make_admin_client()
        songs = _make_songs(2)
        payload = {
            "date": "2026-03-15",
            "plays": [
                {"song_id": songs[0].id, "position": 1, "tone": "G"},
                {"song_id": songs[1].id, "position": 2, "tone": "A"},
            ],
        }
        resp = client.post(URL, payload, format="json")
        assert resp.status_code == 201
        assert resp.data["created"] == 2

        from features.songs.models import Played

        assert Played.objects.filter(date="2026-03-15").count() == 2
