"""Setlist endpoints end to end (specs/017-sunday-setlist-push, contracts/setlist-api.md)."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any

import pytest
from dependency_injector import providers
from django.db.models import ProtectedError
from rest_framework.test import APIClient

from config.di import Container
from conftest import link_to_ministry, make_auth_client, make_role_client, make_user
from core.domain.access import Role
from core.models import DeviceToken
from core.tests.fakes import FakePushSender
from features.accounts.models.user import User
from features.songs.models import Played, Setlist, Song
from features.songs.tests.fakes import FrozenClock

SUNDAY = "2026-10-04"
URL = f"/api/setlists/{SUNDAY}/"
CURRENT = "/api/setlists/current/"
PENDING = "/api/setlists/pending-confirmation/"


@pytest.fixture
def sender(di_container: Container) -> Iterator[FakePushSender]:
    fake = FakePushSender(invalid={"dead-token"})
    with di_container.push_sender.override(providers.Object(fake)):
        yield fake


@contextmanager
def _frozen(container: Container, moment: str) -> Iterator[None]:
    with container.clock.override(providers.Object(FrozenClock(datetime.fromisoformat(moment)))):
        yield


def _songs(n: int = 3) -> list[Song]:
    return [Song.objects.create(title=f"Song {i}", artist=f"Artist {i}") for i in range(1, n + 1)]


def _body(*songs: Song) -> dict[str, Any]:
    return {
        "items": [
            {"song_id": song.pk, "position": index, "tone": "G"}
            for index, song in enumerate(songs, start=1)
        ]
    }


def _leader(username: str = "leader") -> tuple[APIClient, User]:
    client, user = make_role_client(Role.LEADER, username=username)
    link_to_ministry(user)
    return client, user


def _band_member(username: str) -> tuple[APIClient, User]:
    user = make_user(username=username)
    link_to_ministry(user)
    return make_auth_client(user), user


@pytest.mark.django_db
@pytest.mark.usefixtures("sender")
class TestSaveAuthorization:
    def test_anonymous_is_401(self) -> None:
        assert APIClient().put(URL, {}, format="json").status_code == 401

    def test_media_is_403(self) -> None:
        client, user = make_role_client(Role.MEDIA, username="media")
        link_to_ministry(user)
        assert client.put(URL, _body(*_songs(1)), format="json").status_code == 403

    def test_leader_outside_worship_is_403_in_portuguese(self) -> None:
        client, _ = make_role_client(Role.LEADER, username="leader")
        response = client.put(URL, _body(*_songs(1)), format="json")
        assert response.status_code == 403
        assert response.data["detail"] == "Disponível apenas para o ministério de Louvor."
        assert not Setlist.objects.exists()

    def test_admin_in_worship_saves(self) -> None:
        client, user = make_role_client(Role.ADMIN, username="admin")
        link_to_ministry(user)
        assert client.put(URL, _body(*_songs(1)), format="json").status_code == 200


@pytest.mark.django_db
@pytest.mark.usefixtures("sender")
class TestSaveValidation:
    def setup_method(self) -> None:
        self.client, _ = _leader()

    @pytest.mark.parametrize(
        "body",
        [
            [],
            {"items": []},
            {"items": [{"song_id": "x", "position": 1, "tone": "G"}]},
            {"items": [{"song_id": 1, "position": 11, "tone": "G"}]},
            {"items": [{"song_id": 1, "position": 1, "tone": "Bbm7"}]},
        ],
    )
    def test_bad_bodies_are_400(self, body: Any) -> None:
        response = self.client.put(URL, body, format="json")
        assert response.status_code == 400
        assert response.data["error_code"] == "VALIDATION_ERROR"

    def test_bad_date_is_400(self) -> None:
        response = self.client.put("/api/setlists/04-10-2026/", _body(*_songs(1)), format="json")
        assert response.status_code == 400

    def test_monday_is_400_naming_it(self) -> None:
        response = self.client.put("/api/setlists/2026-10-05/", _body(*_songs(1)), format="json")
        assert response.status_code == 400
        assert "Monday" in response.data["detail"]

    def test_repeated_positions_are_400(self) -> None:
        song = _songs(1)[0]
        body = {"items": [{"song_id": song.pk, "position": 1, "tone": "G"}] * 2}
        assert self.client.put(URL, body, format="json").status_code == 400

    def test_unknown_song_is_404_listing_it(self) -> None:
        song = _songs(1)[0]
        body = {"items": [{"song_id": song.pk, "position": 1, "tone": "G"}]}
        body["items"].append({"song_id": 999, "position": 2, "tone": "A"})
        response = self.client.put(URL, body, format="json")
        assert response.status_code == 404
        assert response.data["missing_song_ids"] == [999]
        assert not Setlist.objects.exists()


@pytest.mark.django_db
class TestSaveAndReplace:
    def test_save_answers_the_stored_setlist(self, sender: FakePushSender) -> None:
        client, user = _leader()
        user.profile.name = "Ana Paula"
        user.profile.save()
        first, second = _songs(2)
        response = client.put(URL, _body(first, second), format="json")
        assert response.status_code == 200
        assert response.data["date"] == SUNDAY
        assert response.data["saved_by_name"] == "Ana Paula"
        assert [i["title"] for i in response.data["items"]] == ["Song 1", "Song 2"]

    def test_second_save_replaces_every_item(self, sender: FakePushSender) -> None:
        client, _ = _leader()
        first, second, third = _songs(3)
        client.put(URL, _body(first, second), format="json")
        response = client.put(URL, _body(third), format="json")
        assert [i["song_id"] for i in response.data["items"]] == [third.pk]
        assert Setlist.objects.get().items.count() == 1

    def test_song_in_a_setlist_cannot_be_deleted(self, sender: FakePushSender) -> None:
        client, _ = _leader()
        song = _songs(1)[0]
        client.put(URL, _body(song), format="json")
        with pytest.raises(ProtectedError):
            song.delete()


@pytest.mark.django_db
class TestSavePush:
    def test_only_worship_members_devices_receive_it(self, sender: FakePushSender) -> None:
        client, leader = _leader()
        _, band = _band_member("band")
        outsider = make_user(username="outsider")
        for user, token in ((leader, "leader-phone"), (band, "band-phone"), (outsider, "x")):
            DeviceToken.objects.create(user=user, token=token)
        client.put(URL, _body(*_songs(1)), format="json")
        [(tokens, message)] = sender.calls
        assert sorted(tokens) == ["band-phone", "leader-phone"]
        assert message.as_data() == {"type": "setlist_saved", "date": SUNDAY}

    def test_unregistered_token_is_deleted(self, sender: FakePushSender) -> None:
        client, leader = _leader()
        DeviceToken.objects.create(user=leader, token="dead-token")
        client.put(URL, _body(*_songs(1)), format="json")
        assert not DeviceToken.objects.filter(token="dead-token").exists()

    def test_sender_crash_still_saves(self, di_container: Container) -> None:
        crashing = FakePushSender(raises=RuntimeError("provider down"))
        with di_container.push_sender.override(providers.Object(crashing)):
            client, leader = _leader()
            DeviceToken.objects.create(user=leader, token="leader-phone")
            response = client.put(URL, _body(*_songs(1)), format="json")
        assert response.status_code == 200
        assert Setlist.objects.filter(date=date(2026, 10, 4)).exists()
        assert len(crashing.calls) == 1


@pytest.mark.django_db
@pytest.mark.usefixtures("sender")
class TestCurrent:
    def test_worship_member_gets_the_next_one(self, di_container: Container) -> None:
        leader_client, _ = _leader()
        song = _songs(1)[0]
        for day in ("2026-09-27", "2026-10-04", "2026-10-11"):
            leader_client.put(f"/api/setlists/{day}/", _body(song), format="json")
        band_client, _ = _band_member("band")
        with _frozen(di_container, "2026-10-01T12:00:00-03:00"):
            response = band_client.get(CURRENT)
        assert response.status_code == 200
        assert response.data["setlist"]["date"] == "2026-10-04"
        assert response["Cache-Control"] == "private, no-store"

    def test_none_upcoming_is_null(self) -> None:
        band_client, _ = _band_member("band")
        response = band_client.get(CURRENT)
        assert response.status_code == 200 and response.data == {"setlist": None}

    def test_outsider_is_403(self) -> None:
        client, _ = make_role_client(Role.ADMIN, username="admin")
        assert client.get(CURRENT).status_code == 403


@pytest.mark.django_db
@pytest.mark.usefixtures("sender")
class TestPendingAndByDate:
    def _save_sundays(self, *days: str) -> None:
        client, _ = _leader("saver")
        song = _songs(1)[0]
        for day in days:
            client.put(f"/api/setlists/{day}/", _body(song), format="json")

    def test_pending_newest_first_without_future_or_confirmed(
        self, di_container: Container
    ) -> None:
        self._save_sundays("2026-09-20", "2026-09-27", "2026-10-04", "2026-10-11")
        Played.objects.create(song=Song.objects.get(), tone="G", position=1, date="2026-09-20")
        client, _ = make_role_client(Role.LEADER, username="reader")
        with _frozen(di_container, "2026-10-04T20:00:00-03:00"):
            response = client.get(PENDING)
        assert response.status_code == 200
        assert [s["date"] for s in response.data] == ["2026-10-04", "2026-09-27"]

    def test_pending_today_is_the_local_date(self, di_container: Container) -> None:
        self._save_sundays("2026-09-27", "2026-10-04")
        client, _ = make_role_client(Role.LEADER, username="reader")
        # Saturday 22:00 in Sao Paulo is already Sunday in UTC; Sunday is not pending yet.
        with _frozen(di_container, "2026-10-03T22:00:00-03:00"):
            response = client.get(PENDING)
        assert [s["date"] for s in response.data] == ["2026-09-27"]

    def test_pending_is_empty_list(self) -> None:
        client, _ = make_role_client(Role.ADMIN, username="admin")
        assert client.get(PENDING).data == []

    def test_media_cannot_read(self) -> None:
        self._save_sundays(SUNDAY)
        client, _ = make_role_client(Role.MEDIA, username="media")
        assert client.get(PENDING).status_code == 403
        assert client.get(URL).status_code == 403

    def test_by_date(self) -> None:
        self._save_sundays(SUNDAY)
        client, _ = make_role_client(Role.LEADER, username="reader")
        assert client.get(URL).data["date"] == SUNDAY
        assert client.get("/api/setlists/2026-10-11/").status_code == 404
        assert client.get("/api/setlists/nope/").status_code == 400
