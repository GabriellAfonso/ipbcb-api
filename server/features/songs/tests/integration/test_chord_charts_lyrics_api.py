import pytest
from rest_framework.test import APIClient

from conftest import make_admin_client, make_auth_client, make_role_client, make_user
from core.domain.access import Role
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
class TestChordChartCreateView:
    def test_post_creates_chart(self, song: Song) -> None:
        admin_client, _ = make_admin_client()
        resp = admin_client.post(
            "/api/chord-charts/",
            {"song_id": song.pk, "content": "Am G C", "tone": "G", "instrument": "Violão"},
            format="json",
        )
        assert resp.status_code == 201
        assert resp.data["song_id"] == song.pk
        assert resp.data["content"] == "Am G C"
        assert resp.data["tone"] == "G"
        assert resp.data["instrument"] == "Violão"
        assert "id" in resp.data
        assert "updated_at" in resp.data

    def test_post_returns_400_missing_content(self, song: Song) -> None:
        admin_client, _ = make_admin_client()
        resp = admin_client.post(
            "/api/chord-charts/",
            {"song_id": song.pk, "tone": "G", "instrument": "Violão"},
            format="json",
        )
        assert resp.status_code == 400

    def test_post_returns_400_missing_tone(self, song: Song) -> None:
        admin_client, _ = make_admin_client()
        resp = admin_client.post(
            "/api/chord-charts/",
            {"song_id": song.pk, "content": "Am G C", "instrument": "Violão"},
            format="json",
        )
        assert resp.status_code == 400

    def test_post_returns_400_missing_instrument(self, song: Song) -> None:
        admin_client, _ = make_admin_client()
        resp = admin_client.post(
            "/api/chord-charts/",
            {"song_id": song.pk, "content": "Am G C", "tone": "G"},
            format="json",
        )
        assert resp.status_code == 400

    def test_post_returns_400_nonexistent_song(self) -> None:
        admin_client, _ = make_admin_client()
        resp = admin_client.post(
            "/api/chord-charts/",
            {"song_id": 9999, "content": "Am G C", "tone": "G", "instrument": "Violão"},
            format="json",
        )
        assert resp.status_code == 400

    def test_post_returns_400_missing_song_id(self) -> None:
        admin_client, _ = make_admin_client()
        resp = admin_client.post(
            "/api/chord-charts/",
            {"content": "Am G C", "tone": "G", "instrument": "Violão"},
            format="json",
        )
        assert resp.status_code == 400

    def test_post_returns_401_unauthenticated(self, song: Song) -> None:
        resp = APIClient().post(
            "/api/chord-charts/",
            {"song_id": song.pk, "content": "Am G C", "tone": "G", "instrument": "Violão"},
            format="json",
        )
        assert resp.status_code == 401

    def test_post_returns_403_non_admin(self, song: Song) -> None:
        user = make_user(username="regular_cc")
        auth_client = make_auth_client(user)
        resp = auth_client.post(
            "/api/chord-charts/",
            {"song_id": song.pk, "content": "Am G C", "tone": "G", "instrument": "Violão"},
            format="json",
        )
        assert resp.status_code == 403


@pytest.mark.django_db
class TestChordChartDetailView:
    def test_patch_updates_content(self, song: Song) -> None:
        chart = ChordChart.objects.create(
            song=song, content="Am G C", tone="G", instrument="Violão"
        )
        admin_client, _ = make_admin_client()
        resp = admin_client.patch(
            f"/api/chord-charts/{chart.pk}/", {"content": "D Em C"}, format="json"
        )
        assert resp.status_code == 200
        assert resp.data["content"] == "D Em C"
        assert resp.data["song_id"] == song.pk
        assert resp.data["tone"] == "G"
        assert resp.data["instrument"] == "Violão"
        assert "updated_at" in resp.data

    def test_patch_returns_404_for_nonexistent(self) -> None:
        admin_client, _ = make_admin_client()
        resp = admin_client.patch("/api/chord-charts/9999/", {"content": "X"}, format="json")
        assert resp.status_code == 404

    def test_patch_returns_400_without_content(self, song: Song) -> None:
        chart = ChordChart.objects.create(
            song=song, content="Am G C", tone="G", instrument="Violão"
        )
        admin_client, _ = make_admin_client()
        resp = admin_client.patch(f"/api/chord-charts/{chart.pk}/", {}, format="json")
        assert resp.status_code == 400

    def test_patch_returns_401_unauthenticated(self, song: Song) -> None:
        chart = ChordChart.objects.create(
            song=song, content="Am G C", tone="G", instrument="Violão"
        )
        resp = APIClient().patch(f"/api/chord-charts/{chart.pk}/", {"content": "X"}, format="json")
        assert resp.status_code == 401

    def test_patch_returns_403_non_admin(self, song: Song) -> None:
        chart = ChordChart.objects.create(
            song=song, content="Am G C", tone="G", instrument="Violão"
        )
        user = make_user(username="regular")
        client = make_auth_client(user)
        resp = client.patch(f"/api/chord-charts/{chart.pk}/", {"content": "X"}, format="json")
        assert resp.status_code == 403


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


@pytest.mark.django_db
class TestLyricsCreateView:
    def test_post_creates_lyrics(self, song: Song) -> None:
        admin_client, _ = make_admin_client()
        resp = admin_client.post(
            "/api/lyrics/",
            {"song_id": song.pk, "content": "Amazing grace how sweet the sound"},
            format="json",
        )
        assert resp.status_code == 201
        assert resp.data["song_id"] == song.pk
        assert resp.data["content"] == "Amazing grace how sweet the sound"
        assert "id" in resp.data
        assert "updated_at" in resp.data

    def test_post_returns_400_missing_content(self, song: Song) -> None:
        admin_client, _ = make_admin_client()
        resp = admin_client.post("/api/lyrics/", {"song_id": song.pk}, format="json")
        assert resp.status_code == 400

    def test_post_returns_400_empty_content(self, song: Song) -> None:
        admin_client, _ = make_admin_client()
        resp = admin_client.post("/api/lyrics/", {"song_id": song.pk, "content": ""}, format="json")
        assert resp.status_code == 400

    def test_post_returns_400_nonexistent_song(self) -> None:
        admin_client, _ = make_admin_client()
        resp = admin_client.post(
            "/api/lyrics/", {"song_id": 9999, "content": "Lyrics"}, format="json"
        )
        assert resp.status_code == 400

    def test_post_returns_400_missing_song_id(self) -> None:
        admin_client, _ = make_admin_client()
        resp = admin_client.post("/api/lyrics/", {"content": "Lyrics"}, format="json")
        assert resp.status_code == 400

    def test_post_returns_401_unauthenticated(self, song: Song) -> None:
        resp = APIClient().post(
            "/api/lyrics/",
            {"song_id": song.pk, "content": "Lyrics"},
            format="json",
        )
        assert resp.status_code == 401

    def test_post_returns_403_non_admin(self, song: Song) -> None:
        user = make_user(username="regular_ly")
        auth_client = make_auth_client(user)
        resp = auth_client.post(
            "/api/lyrics/",
            {"song_id": song.pk, "content": "Lyrics"},
            format="json",
        )
        assert resp.status_code == 403


@pytest.mark.django_db
class TestLyricsDetailView:
    def test_patch_updates_content(self, song: Song) -> None:
        lyrics = Lyrics.objects.create(song=song, content="Old content")
        admin_client, _ = make_admin_client()
        resp = admin_client.patch(
            f"/api/lyrics/{lyrics.pk}/", {"content": "New content"}, format="json"
        )
        assert resp.status_code == 200
        assert resp.data["content"] == "New content"
        assert resp.data["song_id"] == song.pk
        assert "updated_at" in resp.data

    def test_patch_returns_404_for_nonexistent(self) -> None:
        admin_client, _ = make_admin_client()
        resp = admin_client.patch("/api/lyrics/9999/", {"content": "X"}, format="json")
        assert resp.status_code == 404

    def test_patch_returns_400_without_content(self, song: Song) -> None:
        lyrics = Lyrics.objects.create(song=song, content="Some content")
        admin_client, _ = make_admin_client()
        resp = admin_client.patch(f"/api/lyrics/{lyrics.pk}/", {}, format="json")
        assert resp.status_code == 400

    def test_patch_returns_401_unauthenticated(self, song: Song) -> None:
        lyrics = Lyrics.objects.create(song=song, content="Some content")
        resp = APIClient().patch(f"/api/lyrics/{lyrics.pk}/", {"content": "X"}, format="json")
        assert resp.status_code == 401

    def test_patch_returns_403_non_admin(self, song: Song) -> None:
        lyrics = Lyrics.objects.create(song=song, content="Some content")
        user = make_user(username="regular2")
        client = make_auth_client(user)
        resp = client.patch(f"/api/lyrics/{lyrics.pk}/", {"content": "X"}, format="json")
        assert resp.status_code == 403


@pytest.mark.django_db
class TestPanelRoles:
    """Liderança holds "manage" on songs; public reads stay public (specs/012)."""

    def test_leader_creates_and_edits_chord_chart(self, song: Song) -> None:
        leader, _ = make_role_client(Role.LEADER)
        created = leader.post(
            "/api/chord-charts/",
            {"song_id": song.pk, "content": "Am", "tone": "Am", "instrument": "Violão"},
            format="json",
        )
        assert created.status_code == 201
        edited = leader.patch(
            f"/api/chord-charts/{created.data['id']}/", {"content": "G"}, format="json"
        )
        assert edited.status_code == 200

    def test_leader_creates_and_edits_lyrics(self, song: Song) -> None:
        leader, _ = make_role_client(Role.LEADER)
        created = leader.post("/api/lyrics/", {"song_id": song.pk, "content": "A"}, format="json")
        assert created.status_code == 201
        edited = leader.patch(f"/api/lyrics/{created.data['id']}/", {"content": "B"}, format="json")
        assert edited.status_code == 200

    def test_media_cannot_create(self, song: Song) -> None:
        media, _ = make_role_client(Role.MEDIA)
        resp = media.post("/api/lyrics/", {"song_id": song.pk, "content": "A"}, format="json")
        assert resp.status_code == 403

    @pytest.mark.parametrize("url", ["/api/chord-charts/", "/api/lyrics/"])
    def test_reads_stay_public(self, client: APIClient, url: str) -> None:
        assert client.get(url).status_code == 200
