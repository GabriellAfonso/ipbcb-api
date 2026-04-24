import pytest
from datetime import date
from rest_framework.test import APIClient

from features.songs.models import Category, Song, Played


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def sample_data() -> dict[str, object]:
    cat = Category.objects.create(name="Worship")
    s1 = Song.objects.create(title="Amazing Grace", artist="Newton", category=cat)
    s2 = Song.objects.create(title="Blessed Be", artist="Matt", category=cat)
    Played.objects.create(song=s1, tone="G", position=1, date=date(2026, 3, 15))
    Played.objects.create(song=s1, tone="G", position=1, date=date(2026, 3, 8))
    Played.objects.create(song=s2, tone="C", position=2, date=date(2026, 3, 15))
    return {"s1": s1, "s2": s2, "cat": cat}


@pytest.mark.django_db
class TestAllSongsAPI:
    def test_lists_songs_with_category(
        self, client: APIClient, sample_data: dict[str, object]
    ) -> None:
        resp = client.get("/api/songs/")
        assert resp.status_code == 200
        assert len(resp.data) == 2
        titles = {s["title"] for s in resp.data}
        assert titles == {"Amazing Grace", "Blessed Be"}
        assert resp.data[0]["category"] == "Worship"

    def test_etag_304(self, client: APIClient, sample_data: dict[str, object]) -> None:
        resp1 = client.get("/api/songs/")
        etag = resp1["ETag"]
        resp2 = client.get("/api/songs/", HTTP_IF_NONE_MATCH=etag)
        assert resp2.status_code == 304


@pytest.mark.django_db
class TestSongsBySundayAPI:
    def test_groups_by_date(self, client: APIClient, sample_data: dict[str, object]) -> None:
        resp = client.get("/api/songs-by-sunday/")
        assert resp.status_code == 200
        dates = [entry["date"] for entry in resp.data]
        assert "15/03/2026" in dates

    def test_etag_304(self, client: APIClient, sample_data: dict[str, object]) -> None:
        resp1 = client.get("/api/songs-by-sunday/")
        etag = resp1["ETag"]
        resp2 = client.get("/api/songs-by-sunday/", HTTP_IF_NONE_MATCH=etag)
        assert resp2.status_code == 304


@pytest.mark.django_db
class TestTopSongsAPI:
    def test_returns_counts_ordered_desc(
        self, client: APIClient, sample_data: dict[str, object]
    ) -> None:
        resp = client.get("/api/top-songs/")
        assert resp.status_code == 200
        assert len(resp.data) == 2
        assert resp.data[0]["play_count"] >= resp.data[1]["play_count"]
        assert resp.data[0]["song__title"] == "Amazing Grace"


@pytest.mark.django_db
class TestTopTonesAPI:
    def test_returns_tone_counts(self, client: APIClient, sample_data: dict[str, object]) -> None:
        resp = client.get("/api/top-tones/")
        assert resp.status_code == 200
        tones = {item["tone"] for item in resp.data}
        assert "G" in tones
