from datetime import datetime, time
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from rest_framework.test import APIClient

from conftest import make_admin_client, make_auth_client, make_role_client, make_user
from core.domain.access import Role
from features.songs.models.hymnal import Hymn
from core.models import ChurchService
from features.songs.models.hymnal_history import (
    HymnalHistorySettings,
    HymnalViewEvent,
)

SETTINGS_URL = "/api/hymnal-history/settings/"
WINDOWS_URL = "/api/hymnal-history/service-windows/"
TOP_HYMNS_URL = "/api/hymnal-history/top-hymns/"

SAO_PAULO = ZoneInfo("America/Sao_Paulo")
SUNDAY_EVENING = datetime(2026, 8, 9, 19, 30, tzinfo=SAO_PAULO)


@pytest.fixture(autouse=True)
def _isolate_from_seeded_windows(db: None) -> None:
    """Migration core.0003 seeds the church's real windows. The CRUD tests assert on
    exact list contents, so they start from an empty table."""
    ChurchService.objects.all().delete()


def _window_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Culto de Domingo à Noite",
        "weekday": 1,
        "start_time": "19:00",
        "end_time": "21:00",
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
class TestSettingsRead:
    def test_anonymous_read_returns_the_defaults_on_an_empty_database(self) -> None:
        resp = APIClient().get(SETTINGS_URL)

        assert resp.status_code == 200
        assert resp.data == {
            "min_seconds_to_count": 30,
            "collapse_window_minutes": 10,
            "max_batch_size": 200,
            "max_past_days": 90,
            "future_tolerance_minutes": 5,
            "window_grace_minutes": 30,
        }

    def test_reading_materialises_exactly_one_row(self) -> None:
        APIClient().get(SETTINGS_URL)
        APIClient().get(SETTINGS_URL)

        assert HymnalHistorySettings.objects.count() == 1


@pytest.mark.django_db
class TestSettingsUpdate:
    def test_anonymous_patch_is_401(self) -> None:
        resp = APIClient().patch(SETTINGS_URL, {"min_seconds_to_count": 45}, format="json")
        assert resp.status_code == 401

    def test_non_admin_patch_is_403(self) -> None:
        client = make_auth_client(make_user())
        resp = client.patch(SETTINGS_URL, {"min_seconds_to_count": 45}, format="json")
        assert resp.status_code == 403

    def test_admin_patch_updates_the_value(self) -> None:
        client, _ = make_admin_client()

        resp = client.patch(SETTINGS_URL, {"min_seconds_to_count": 45}, format="json")

        assert resp.status_code == 200
        assert resp.data["min_seconds_to_count"] == 45
        assert APIClient().get(SETTINGS_URL).data["min_seconds_to_count"] == 45

    def test_patch_is_partial(self) -> None:
        client, _ = make_admin_client()

        client.patch(SETTINGS_URL, {"min_seconds_to_count": 45}, format="json")
        resp = client.patch(SETTINGS_URL, {"max_batch_size": 50}, format="json")

        assert resp.data["min_seconds_to_count"] == 45
        assert resp.data["max_batch_size"] == 50

    @pytest.mark.parametrize(
        "field,value",
        [
            ("min_seconds_to_count", 0),
            ("min_seconds_to_count", 3601),
            ("collapse_window_minutes", 0),
            ("collapse_window_minutes", 1441),
            ("max_batch_size", 0),
            ("max_batch_size", 1001),
            ("max_past_days", 0),
            ("max_past_days", 3651),
            ("future_tolerance_minutes", 0),
            ("future_tolerance_minutes", 1441),
            ("window_grace_minutes", 0),
            ("window_grace_minutes", 1441),
        ],
    )
    def test_out_of_range_values_are_rejected(self, field: str, value: int) -> None:
        client, _ = make_admin_client()

        resp = client.patch(SETTINGS_URL, {field: value}, format="json")

        assert resp.status_code == 400
        assert resp.data["error_code"] == "VALIDATION_ERROR"
        message = resp.data["field_errors"][field][0]
        assert str(value) in message
        assert "out of range" in message

    def test_negative_value_is_rejected(self) -> None:
        client, _ = make_admin_client()
        resp = client.patch(SETTINGS_URL, {"max_past_days": -5}, format="json")
        assert resp.status_code == 400

    def test_non_integer_value_is_rejected(self) -> None:
        client, _ = make_admin_client()
        resp = client.patch(SETTINGS_URL, {"max_past_days": "many"}, format="json")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestSettingsChangesNeverRewriteHistory:
    def test_stored_events_and_counts_are_unchanged(self) -> None:
        client, _ = make_admin_client()
        hymn = Hymn.objects.create(number="50", title="Hino 50", lyrics=[])
        ChurchService.objects.create(
            name="Noite", weekday=1, start_time=time(19, 0), end_time=time(21, 0)
        )
        event = HymnalViewEvent.objects.create(
            client_event_id=uuid4(),
            hymn=hymn,
            device_id="dev-a",
            viewed_at=SUNDAY_EVENING,
            duration_seconds=3,
        )
        before = client.get(TOP_HYMNS_URL).data["hymns"]

        client.patch(SETTINGS_URL, {"min_seconds_to_count": 600}, format="json")

        after = client.get(TOP_HYMNS_URL).data["hymns"]
        event.refresh_from_db()
        assert after == before
        assert event.duration_seconds == 3
        assert HymnalViewEvent.objects.count() == 1


@pytest.mark.django_db
class TestServiceWindowAuth:
    def test_anonymous_list_is_401(self) -> None:
        assert APIClient().get(WINDOWS_URL).status_code == 401

    def test_non_admin_list_is_403(self) -> None:
        client = make_auth_client(make_user())
        assert client.get(WINDOWS_URL).status_code == 403

    def test_non_admin_create_is_403(self) -> None:
        client = make_auth_client(make_user())
        assert client.post(WINDOWS_URL, _window_payload(), format="json").status_code == 403


@pytest.mark.django_db
class TestServiceWindowCrud:
    def setup_method(self) -> None:
        self.client, _ = make_admin_client()

    def test_create_then_list(self) -> None:
        created = self.client.post(WINDOWS_URL, _window_payload(), format="json")

        assert created.status_code == 201
        assert created.data["weekday"] == 1
        assert created.data["active"] is True

        listed = self.client.get(WINDOWS_URL)
        assert len(listed.data["service_windows"]) == 1

    def test_retrieve(self) -> None:
        created = self.client.post(WINDOWS_URL, _window_payload(), format="json")

        resp = self.client.get(f"{WINDOWS_URL}{created.data['id']}/")

        assert resp.status_code == 200
        assert resp.data["name"] == "Culto de Domingo à Noite"

    def test_patch(self) -> None:
        created = self.client.post(WINDOWS_URL, _window_payload(), format="json")

        resp = self.client.patch(
            f"{WINDOWS_URL}{created.data['id']}/", {"start_time": "18:30"}, format="json"
        )

        assert resp.status_code == 200
        assert resp.data["start_time"] == "18:30:00"
        assert resp.data["end_time"] == "21:00:00"

    def test_patch_can_deactivate(self) -> None:
        created = self.client.post(WINDOWS_URL, _window_payload(), format="json")

        resp = self.client.patch(
            f"{WINDOWS_URL}{created.data['id']}/", {"active": False}, format="json"
        )

        assert resp.data["active"] is False

    def test_delete(self) -> None:
        created = self.client.post(WINDOWS_URL, _window_payload(), format="json")

        resp = self.client.delete(f"{WINDOWS_URL}{created.data['id']}/")

        assert resp.status_code == 204
        assert ChurchService.objects.count() == 0

    def test_missing_id_is_404(self) -> None:
        resp = self.client.get(f"{WINDOWS_URL}99999/")

        assert resp.status_code == 404
        assert resp.data["error_code"] == "NOT_FOUND"
        assert resp.data["window_id"] == 99999

    def test_list_is_ordered_by_weekday_then_start_time(self) -> None:
        self.client.post(WINDOWS_URL, _window_payload(name="Noite"), format="json")
        self.client.post(
            WINDOWS_URL,
            _window_payload(name="Manhã", start_time="09:00", end_time="10:30"),
            format="json",
        )
        self.client.post(
            WINDOWS_URL,
            _window_payload(name="Quarta", weekday=4, start_time="19:30", end_time="21:00"),
            format="json",
        )

        # Sunday is 1 and Wednesday is 4, so both Sunday services come first,
        # ordered by start time.
        names = [w["name"] for w in self.client.get(WINDOWS_URL).data["service_windows"]]
        assert names == ["Manhã", "Noite", "Quarta"]


@pytest.mark.django_db
class TestServiceWindowValidation:
    def setup_method(self) -> None:
        self.client, _ = make_admin_client()

    def test_end_time_before_start_time_is_400(self) -> None:
        resp = self.client.post(
            WINDOWS_URL,
            _window_payload(start_time="21:00", end_time="19:00"),
            format="json",
        )

        assert resp.status_code == 400
        message = resp.data["field_errors"]["end_time"][0]
        assert "19:00" in message and "21:00" in message

    def test_end_time_equal_to_start_time_is_400(self) -> None:
        resp = self.client.post(
            WINDOWS_URL,
            _window_payload(start_time="19:00", end_time="19:00"),
            format="json",
        )
        assert resp.status_code == 400

    @pytest.mark.parametrize("weekday", [-1, 0, 8, 99])
    def test_weekday_out_of_range_is_400(self, weekday: int) -> None:
        resp = self.client.post(WINDOWS_URL, _window_payload(weekday=weekday), format="json")

        assert resp.status_code == 400
        message = resp.data["field_errors"]["weekday"][0]
        assert str(weekday) in message
        assert "Sunday" in message and "Saturday" in message

    def test_patch_that_would_invert_the_range_is_400_not_500(self) -> None:
        """Merged against the stored row, so this never reaches the DB constraint."""
        created = self.client.post(WINDOWS_URL, _window_payload(), format="json")

        resp = self.client.patch(
            f"{WINDOWS_URL}{created.data['id']}/", {"start_time": "22:00"}, format="json"
        )

        assert resp.status_code == 400

    def test_blank_name_is_400(self) -> None:
        resp = self.client.post(WINDOWS_URL, _window_payload(name=""), format="json")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestDeletingAWindowKeepsHistory:
    def test_events_survive(self) -> None:
        client, _ = make_admin_client()
        hymn = Hymn.objects.create(number="50", title="Hino 50", lyrics=[])
        created = client.post(WINDOWS_URL, _window_payload(), format="json")
        HymnalViewEvent.objects.create(
            client_event_id=uuid4(),
            hymn=hymn,
            device_id="dev-a",
            viewed_at=SUNDAY_EVENING,
            duration_seconds=40,
        )

        client.delete(f"{WINDOWS_URL}{created.data['id']}/")

        assert HymnalViewEvent.objects.count() == 1


@pytest.mark.django_db
class TestPanelRoles:
    """Configuration writes are owner-only by override; reads are "view"
    (specs/012-feature-role-permissions, Endpoint Classification)."""

    def test_leader_cannot_change_settings(self) -> None:
        client, _ = make_role_client(Role.LEADER)
        resp = client.patch(SETTINGS_URL, {"min_seconds_to_count": 45}, format="json")
        assert resp.status_code == 403

    def test_admin_changes_settings(self) -> None:
        client, _ = make_role_client(Role.ADMIN)
        resp = client.patch(SETTINGS_URL, {"min_seconds_to_count": 45}, format="json")
        assert resp.status_code == 200
        assert resp.data["min_seconds_to_count"] == 45

    @pytest.mark.parametrize("role", [Role.LEADER, Role.MEDIA])
    def test_panel_roles_read_windows(self, role: Role) -> None:
        client, _ = make_role_client(role)
        assert client.get(WINDOWS_URL).status_code == 200

    def test_leader_cannot_create_window(self) -> None:
        client, _ = make_role_client(Role.LEADER)
        resp = client.post(WINDOWS_URL, _window_payload(), format="json")
        assert resp.status_code == 403
        assert not ChurchService.objects.exists()
