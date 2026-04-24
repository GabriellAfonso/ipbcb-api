import pytest
from rest_framework.test import APIClient

from features.songs.models import Song, ChordChart, Lyrics


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def song() -> Song:
    return Song.objects.create(title="Oceans", artist="Hillsong")


@pytest.mark.django_db
class TestChordChartListView:
    def test_returns_200(self, client: APIClient, song: Song) -> None:
        ChordChart.objects.create(song=song, content="Am G C", tone="Am", instrument="Guitar")
        resp = client.get("/api/chord-charts/")
        assert resp.status_code == 200
        assert len(resp.data) == 1
        assert resp.data[0]["tone"] == "Am"

    def test_empty_list(self, client: APIClient) -> None:
        resp = client.get("/api/chord-charts/")
        assert resp.status_code == 200
        assert resp.data == []


@pytest.mark.django_db
class TestLyricsListView:
    def test_returns_200(self, client: APIClient, song: Song) -> None:
        Lyrics.objects.create(song=song, content="Amazing grace how sweet the sound")
        resp = client.get("/api/lyrics/")
        assert resp.status_code == 200
        assert len(resp.data) == 1
        assert "Amazing grace" in resp.data[0]["content"]

    def test_empty_list(self, client: APIClient) -> None:
        resp = client.get("/api/lyrics/")
        assert resp.status_code == 200
        assert resp.data == []
