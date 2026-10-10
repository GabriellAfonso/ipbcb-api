from datetime import date, datetime, timezone

import pytest
from rest_framework.test import APIClient

from conftest import make_admin_client, make_role_client
from core.domain.access import Role
from features.songs.models import Category, Song, Played
from features.songs.models.chord_chart import ChordChart
from features.songs.models.lyrics import Lyrics
from features.songs.models.setlist import Setlist, SetlistItem

MISSING = 999_999


@pytest.fixture
def song() -> Song:
    category = Category.objects.create(name="Worship")
    return Song.objects.create(
        title="Ocenas", artist="Hillsong", category=category, youtube_link="https://youtu.be/a"
    )


@pytest.fixture
def leader() -> APIClient:
    client, _ = make_role_client(Role.LEADER, username="leader")
    return client


@pytest.fixture
def admin() -> APIClient:
    client, _ = make_admin_client()
    return client


def _url(song_id: int) -> str:
    return f"/api/songs/{song_id}/"


def _play(song: Song, day: date) -> Played:
    return Played.objects.create(song=song, tone="G", position=1, date=day)


def _setlist(song: Song, day: date) -> None:
    setlist = Setlist.objects.create(date=day, saved_at=datetime(2026, 10, 10, tzinfo=timezone.utc))
    SetlistItem.objects.create(setlist=setlist, position=1, song=song, tone="G")


@pytest.mark.django_db
class TestEditSongAPI:
    def test_edits_one_field_and_answers_list_shape(self, leader: APIClient, song: Song) -> None:
        resp = leader.patch(_url(song.pk), {"title": "Oceans"}, format="json")
        assert resp.status_code == 200
        assert resp.data == {
            "id": song.pk,
            "title": "Oceans",
            "artist": "Hillsong",
            "category": "Worship",
            "youtube_link": "https://youtu.be/a",
        }
        song.refresh_from_db()
        assert (song.title, song.artist) == ("Oceans", "Hillsong")

    def test_category_is_empty_string_when_none(self, leader: APIClient) -> None:
        bare = Song.objects.create(title="A", artist="B")
        resp = leader.patch(_url(bare.pk), {"artist": "C"}, format="json")
        assert resp.data["category"] == ""

    def test_empty_link_clears_it(self, leader: APIClient, song: Song) -> None:
        resp = leader.patch(_url(song.pk), {"youtube_link": ""}, format="json")
        assert resp.status_code == 200
        song.refresh_from_db()
        assert (song.youtube_link, song.title) == ("", "Ocenas")

    @pytest.mark.parametrize(
        ("body", "field"),
        [
            ({"category": "x"}, "category"),
            ({"title": None}, "title"),
            ({"youtube_link": "not a url"}, "youtube_link"),
        ],
    )
    def test_invalid_body_is_400_on_the_field(
        self, leader: APIClient, song: Song, body: dict[str, object], field: str
    ) -> None:
        resp = leader.patch(_url(song.pk), body, format="json")
        assert resp.status_code == 400
        assert resp.data["error_code"] == "VALIDATION_ERROR"
        assert field in resp.data["field_errors"]

    def test_empty_body_is_400(self, leader: APIClient, song: Song) -> None:
        resp = leader.patch(_url(song.pk), {}, format="json")
        assert resp.status_code == 400
        assert resp.data["error_code"] == "VALIDATION_ERROR"

    def test_duplicate_of_another_song_is_409(self, leader: APIClient, song: Song) -> None:
        Song.objects.create(title="Oceans", artist="Hillsong")
        resp = leader.patch(_url(song.pk), {"title": "OCEANS"}, format="json")
        assert resp.status_code == 409
        assert (resp.data["title"], resp.data["artist"]) == ("OCEANS", "Hillsong")
        song.refresh_from_db()
        assert song.title == "Ocenas"

    def test_case_only_change_is_fine(self, leader: APIClient, song: Song) -> None:
        resp = leader.patch(_url(song.pk), {"title": "OCENAS"}, format="json")
        assert resp.status_code == 200

    def test_unknown_id_is_404(self, leader: APIClient) -> None:
        resp = leader.patch(_url(MISSING), {"title": "X"}, format="json")
        assert resp.status_code == 404
        assert resp.data["song_id"] == MISSING

    def test_anonymous_is_401(self, song: Song) -> None:
        assert APIClient().patch(_url(song.pk), {"title": "X"}, format="json").status_code == 401

    def test_media_is_403(self, song: Song) -> None:
        # No role holds "view" on songs; Mídia holds nothing there (spec 012 scope matrix).
        media, _ = make_role_client(Role.MEDIA, username="media")
        assert media.patch(_url(song.pk), {"title": "X"}, format="json").status_code == 403


@pytest.mark.django_db
class TestSongDataCachesAfterEdit:
    """The ETag is a hash of the body, so an edit must change it (spec 018 FR-018)."""

    @pytest.mark.parametrize("url", ["/api/songs/", "/api/songs-by-sunday/", "/api/top-songs/"])
    def test_old_etag_gets_the_new_title(self, leader: APIClient, song: Song, url: str) -> None:
        _play(song, date(2026, 3, 15))
        old_etag = APIClient().get(url)["ETag"]
        leader.patch(_url(song.pk), {"title": "Oceans"}, format="json")
        resp = APIClient().get(url, HTTP_IF_NONE_MATCH=old_etag)
        assert resp.status_code == 200
        assert "Oceans" in resp.content.decode()


@pytest.mark.django_db
class TestDeleteSongAPI:
    def test_owner_deletes_song_with_charts_and_lyrics(self, admin: APIClient, song: Song) -> None:
        ChordChart.objects.create(song=song, content="Am", tone="Am", instrument="Violão")
        Lyrics.objects.create(song=song, content="Oceans")
        resp = admin.delete(_url(song.pk))
        assert resp.status_code == 204
        assert not resp.content
        assert not Song.objects.filter(pk=song.pk).exists()
        assert not ChordChart.objects.filter(song_id=song.pk).exists()
        assert not Lyrics.objects.filter(song_id=song.pk).exists()

    def test_unknown_id_is_404(self, admin: APIClient) -> None:
        resp = admin.delete(_url(MISSING))
        assert resp.status_code == 404
        assert resp.data["song_id"] == MISSING

    def test_anonymous_is_401(self, song: Song) -> None:
        assert APIClient().delete(_url(song.pk)).status_code == 401

    def test_media_is_403(self, song: Song) -> None:
        media, _ = make_role_client(Role.MEDIA, username="media")
        assert media.delete(_url(song.pk)).status_code == 403

    def test_manage_is_not_enough(self, leader: APIClient, song: Song) -> None:
        assert leader.delete(_url(song.pk)).status_code == 403
        assert Song.objects.filter(pk=song.pk).exists()


@pytest.mark.django_db
class TestBlockedDeleteAPI:
    def _assert_untouched(self, song: Song, plays: int, setlists: int) -> None:
        assert Song.objects.filter(pk=song.pk).exists()
        assert Played.objects.filter(song=song).count() == plays
        assert SetlistItem.objects.filter(song=song).count() == setlists
        assert Setlist.objects.count() == setlists
        assert ChordChart.objects.filter(song=song).count() == 1
        assert Lyrics.objects.filter(song=song).count() == 1

    @pytest.fixture(autouse=True)
    def _owned_content(self, song: Song) -> None:
        ChordChart.objects.create(song=song, content="Am", tone="Am", instrument="Violão")
        Lyrics.objects.create(song=song, content="Oceans")

    def test_plays_and_setlist(self, admin: APIClient, song: Song) -> None:
        _play(song, date(2026, 3, 8))
        _play(song, date(2026, 3, 15))
        _setlist(song, date(2026, 10, 18))
        resp = admin.delete(_url(song.pk))
        assert resp.status_code == 409
        assert resp.data == {
            "error_code": "CONFLICT",
            "detail": 'A música "Ocenas" não pode ser excluída: foi tocada em 2 domingos '
            "e está na setlist de 18/10/2026.",
            "song_id": song.pk,
            "title": "Ocenas",
            "plays": 2,
            "setlist_dates": ["2026-10-18"],
        }
        self._assert_untouched(song, plays=2, setlists=1)

    def test_plays_only(self, admin: APIClient, song: Song) -> None:
        _play(song, date(2026, 3, 8))
        resp = admin.delete(_url(song.pk))
        assert resp.status_code == 409
        assert resp.data["detail"].endswith("foi tocada em 1 domingo.")
        assert resp.data["setlist_dates"] == []
        self._assert_untouched(song, plays=1, setlists=0)

    def test_setlist_only(self, admin: APIClient, song: Song) -> None:
        _setlist(song, date(2026, 10, 18))
        resp = admin.delete(_url(song.pk))
        assert resp.status_code == 409
        assert resp.data["detail"].endswith("excluída: está na setlist de 18/10/2026.")
        assert resp.data["plays"] == 0
        self._assert_untouched(song, plays=0, setlists=1)
