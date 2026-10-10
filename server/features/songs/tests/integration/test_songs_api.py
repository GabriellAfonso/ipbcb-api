import pytest
from datetime import date
from rest_framework.test import APIClient

from conftest import make_admin_client, make_auth_client, make_user
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
class TestCreateSongAPI:
    def test_creates_song_and_returns_201(self) -> None:
        admin_client, _ = make_admin_client()
        resp = admin_client.post(
            "/api/songs/",
            {"title": "  Oceans ", "artist": "Hillsong", "youtube_link": "https://youtu.be/x"},
            format="json",
        )
        assert resp.status_code == 201
        assert resp.data["title"] == "Oceans"
        assert resp.data["artist"] == "Hillsong"
        assert resp.data["youtube_link"] == "https://youtu.be/x"
        assert resp.data["category"] == ""
        assert Song.objects.filter(pk=resp.data["id"]).exists()

    def test_youtube_link_is_optional(self) -> None:
        admin_client, _ = make_admin_client()
        resp = admin_client.post(
            "/api/songs/", {"title": "Oceans", "artist": "Hillsong"}, format="json"
        )
        assert resp.status_code == 201
        assert resp.data["youtube_link"] == ""

    @pytest.mark.parametrize(
        "body",
        [
            {"artist": "Hillsong"},
            {"title": "Oceans"},
            {"title": "   ", "artist": "Hillsong"},
            {"title": "Oceans", "artist": ""},
            {"title": "x" * 101, "artist": "Hillsong"},
            {"title": "Oceans", "artist": "x" * 101},
            {"title": "Oceans", "artist": "Hillsong", "youtube_link": "not a url"},
        ],
    )
    def test_returns_400_for_invalid_body(self, body: dict[str, str]) -> None:
        admin_client, _ = make_admin_client()
        resp = admin_client.post("/api/songs/", body, format="json")
        assert resp.status_code == 400
        assert resp.data["error_code"] == "VALIDATION_ERROR"
        assert not Song.objects.exists()

    def test_returns_409_for_same_title_and_artist_ignoring_case(self) -> None:
        Song.objects.create(title="Oceans", artist="Hillsong")
        admin_client, _ = make_admin_client()
        resp = admin_client.post(
            "/api/songs/", {"title": "OCEANS", "artist": " hillsong "}, format="json"
        )
        assert resp.status_code == 409
        assert resp.data["error_code"] == "CONFLICT"
        assert Song.objects.count() == 1

    def test_same_title_by_another_artist_is_allowed(self) -> None:
        Song.objects.create(title="Oceans", artist="Hillsong")
        admin_client, _ = make_admin_client()
        resp = admin_client.post(
            "/api/songs/", {"title": "Oceans", "artist": "Other"}, format="json"
        )
        assert resp.status_code == 201

    def test_returns_401_unauthenticated(self, client: APIClient) -> None:
        resp = client.post("/api/songs/", {"title": "Oceans", "artist": "Hillsong"}, format="json")
        assert resp.status_code == 401
        assert not Song.objects.exists()

    def test_returns_403_without_songs_manage(self) -> None:
        auth_client = make_auth_client(make_user(username="no_songs_scope"))
        resp = auth_client.post(
            "/api/songs/", {"title": "Oceans", "artist": "Hillsong"}, format="json"
        )
        assert resp.status_code == 403
        assert not Song.objects.exists()


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
