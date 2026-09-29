from datetime import datetime, time
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from rest_framework.test import APIClient

from conftest import make_admin_client, make_auth_client, make_role_client, make_user
from core.domain.access import Role
from features.songs.models.hymnal import Hymn
from core.models import ChurchService
from features.songs.models.hymnal_history import HymnalViewEvent

OCCURRENCES_URL = "/api/hymnal-history/occurrences/"
TOP_HYMNS_URL = "/api/hymnal-history/top-hymns/"

SAO_PAULO = ZoneInfo("America/Sao_Paulo")
SUNDAY_EVENING = datetime(2026, 8, 9, 19, 30, tzinfo=SAO_PAULO)
SUNDAY_MORNING = datetime(2026, 8, 9, 10, 45, tzinfo=SAO_PAULO)
WEDNESDAY_AFTERNOON = datetime(2026, 8, 12, 15, 0, tzinfo=SAO_PAULO)


@pytest.fixture(autouse=True)
def _isolate_from_seeded_windows(db: None) -> None:
    """Migration core.0003 seeds the church's real windows. These tests assert on an
    exact set of occurrences, so they start from an empty table."""
    ChurchService.objects.all().delete()


def _hymn(number: str = "50") -> Hymn:
    return Hymn.objects.create(number=number, title=f"Hino {number}", lyrics=[])


def _evening_window() -> ChurchService:
    return ChurchService.objects.create(
        name="Culto de Domingo à Noite",
        weekday=1,
        start_time=time(19, 0),
        end_time=time(21, 0),
    )


def _store(hymn: Hymn, moment: datetime, device_id: str) -> HymnalViewEvent:
    """Seed history directly through the ORM — no dependency on the ingest endpoint."""
    return HymnalViewEvent.objects.create(
        client_event_id=uuid4(),
        hymn=hymn,
        device_id=device_id,
        viewed_at=moment,
        duration_seconds=40,
    )


@pytest.mark.django_db
class TestReportsAuth:
    def test_occurrences_anonymous_is_401(self) -> None:
        assert APIClient().get(OCCURRENCES_URL).status_code == 401

    def test_occurrences_non_admin_is_403(self) -> None:
        client = make_auth_client(make_user())
        assert client.get(OCCURRENCES_URL).status_code == 403

    def test_top_hymns_anonymous_is_401(self) -> None:
        assert APIClient().get(TOP_HYMNS_URL).status_code == 401

    def test_top_hymns_non_admin_is_403(self) -> None:
        client = make_auth_client(make_user())
        assert client.get(TOP_HYMNS_URL).status_code == 403

    def test_admin_gets_200(self) -> None:
        client, _ = make_admin_client()
        assert client.get(OCCURRENCES_URL).status_code == 200
        assert client.get(TOP_HYMNS_URL).status_code == 200


@pytest.mark.django_db
class TestOccurrences:
    def setup_method(self) -> None:
        self.client, _ = make_admin_client()

    def test_three_devices_in_one_service_are_one_occurrence(self) -> None:
        hymn = _hymn()
        window = _evening_window()
        for device in ("dev-a", "dev-b", "dev-c"):
            _store(hymn, SUNDAY_EVENING, device)

        resp = self.client.get(f"{OCCURRENCES_URL}?from=2026-08-01&to=2026-08-31")

        assert resp.status_code == 200
        occurrences = resp.data["occurrences"]
        assert len(occurrences) == 1
        assert occurrences[0]["device_count"] == 3
        assert occurrences[0]["service_window_id"] == window.id
        assert occurrences[0]["hymn_number"] == "50"

    def test_morning_and_evening_are_two_occurrences(self) -> None:
        hymn = _hymn()
        _evening_window()
        ChurchService.objects.create(
            name="Manhã", weekday=1, start_time=time(10, 30), end_time=time(12, 0)
        )
        _store(hymn, SUNDAY_MORNING, "dev-a")
        _store(hymn, SUNDAY_EVENING, "dev-a")

        resp = self.client.get(f"{OCCURRENCES_URL}?from=2026-08-01&to=2026-08-31")

        assert len(resp.data["occurrences"]) == 2

    def test_outside_every_window_collapses_by_day(self) -> None:
        hymn = _hymn("120")
        _evening_window()
        _store(hymn, WEDNESDAY_AFTERNOON, "dev-a")
        _store(hymn, WEDNESDAY_AFTERNOON, "dev-b")

        resp = self.client.get(f"{OCCURRENCES_URL}?from=2026-08-01&to=2026-08-31")

        occurrence = resp.data["occurrences"][0]
        assert occurrence["service_window_id"] is None
        assert occurrence["service_window_name"] is None
        assert occurrence["bucket"] == "2026-08-12:none"
        assert occurrence["device_count"] == 2

    def test_grouping_changes_only_the_bucket_label(self) -> None:
        hymn = _hymn()
        _evening_window()
        _store(hymn, SUNDAY_EVENING, "dev-a")

        buckets = {}
        for group_by in ("service", "day", "week", "month"):
            resp = self.client.get(
                f"{OCCURRENCES_URL}?from=2026-08-01&to=2026-08-31&group_by={group_by}"
            )
            assert len(resp.data["occurrences"]) == 1
            buckets[group_by] = resp.data["occurrences"][0]["bucket"]

        assert buckets["day"] == "2026-08-09"
        assert buckets["week"] == "2026-W32"
        assert buckets["month"] == "2026-08"
        assert buckets["service"].endswith(":1") or ":" in buckets["service"]

    def test_defaults_to_the_last_30_days(self) -> None:
        resp = self.client.get(OCCURRENCES_URL)
        assert resp.status_code == 200
        assert (resp.data["to"] - resp.data["from"]).days == 30

    def test_from_after_to_is_400(self) -> None:
        resp = self.client.get(f"{OCCURRENCES_URL}?from=2026-08-10&to=2026-08-09")
        assert resp.status_code == 400
        assert resp.data["error_code"] == "VALIDATION_ERROR"

    def test_span_over_366_days_is_400(self) -> None:
        resp = self.client.get(f"{OCCURRENCES_URL}?from=2024-01-01&to=2026-08-09")
        assert resp.status_code == 400
        assert "366" in resp.data["detail"]

    def test_unknown_group_by_is_400(self) -> None:
        resp = self.client.get(f"{OCCURRENCES_URL}?group_by=decade")
        assert resp.status_code == 400

    def test_unparseable_date_is_400(self) -> None:
        resp = self.client.get(f"{OCCURRENCES_URL}?from=09/08/2026")
        assert resp.status_code == 400

    def test_events_outside_the_range_are_excluded(self) -> None:
        hymn = _hymn()
        _evening_window()
        _store(hymn, SUNDAY_EVENING, "dev-a")

        resp = self.client.get(f"{OCCURRENCES_URL}?from=2026-09-01&to=2026-09-30")

        assert resp.data["occurrences"] == []


@pytest.mark.django_db
class TestOccurrencesSurviveWindowChanges:
    def test_deleting_a_window_regroups_without_losing_events(self) -> None:
        client, _ = make_admin_client()
        hymn = _hymn()
        window = _evening_window()
        _store(hymn, SUNDAY_EVENING, "dev-a")

        before = client.get(f"{OCCURRENCES_URL}?from=2026-08-01&to=2026-08-31")
        assert before.data["occurrences"][0]["service_window_id"] == window.id

        window.delete()

        after = client.get(f"{OCCURRENCES_URL}?from=2026-08-01&to=2026-08-31")
        assert after.data["occurrences"][0]["service_window_id"] is None
        assert HymnalViewEvent.objects.count() == 1

    def test_deactivating_a_window_regroups_too(self) -> None:
        client, _ = make_admin_client()
        hymn = _hymn()
        window = _evening_window()
        _store(hymn, SUNDAY_EVENING, "dev-a")

        window.active = False
        window.save()

        resp = client.get(f"{OCCURRENCES_URL}?from=2026-08-01&to=2026-08-31")
        assert resp.data["occurrences"][0]["service_window_id"] is None


@pytest.mark.django_db
class TestTopHymns:
    def setup_method(self) -> None:
        self.client, _ = make_admin_client()

    def test_counts_occurrences_not_events(self) -> None:
        hymn = _hymn()
        _evening_window()
        for device in ("dev-a", "dev-b", "dev-c", "dev-d", "dev-e"):
            _store(hymn, SUNDAY_EVENING, device)

        resp = self.client.get(TOP_HYMNS_URL)

        assert resp.status_code == 200
        assert resp.data["hymns"] == [
            {"hymn_number": "50", "hymn_title": "Hino 50", "occurrence_count": 1}
        ]

    def test_ordered_by_count_descending(self) -> None:
        popular = _hymn("50")
        rare = _hymn("120")
        _evening_window()
        _store(popular, SUNDAY_EVENING, "dev-a")
        _store(popular, datetime(2026, 8, 16, 19, 30, tzinfo=SAO_PAULO), "dev-a")
        _store(rare, SUNDAY_EVENING, "dev-a")

        resp = self.client.get(TOP_HYMNS_URL)

        assert [h["hymn_number"] for h in resp.data["hymns"]] == ["50", "120"]
        assert resp.data["hymns"][0]["occurrence_count"] == 2

    def test_hymns_without_occurrences_are_absent(self) -> None:
        viewed = _hymn("50")
        _hymn("120")
        _evening_window()
        _store(viewed, SUNDAY_EVENING, "dev-a")

        resp = self.client.get(TOP_HYMNS_URL)

        assert [h["hymn_number"] for h in resp.data["hymns"]] == ["50"]

    def test_defaults_to_all_time(self) -> None:
        hymn = _hymn()
        _evening_window()
        _store(hymn, datetime(2020, 8, 9, 19, 30, tzinfo=SAO_PAULO), "dev-a")

        resp = self.client.get(TOP_HYMNS_URL)

        assert resp.data["from"] is None
        assert resp.data["to"] is None
        assert len(resp.data["hymns"]) == 1

    def test_range_filters_the_count(self) -> None:
        hymn = _hymn()
        _evening_window()
        _store(hymn, SUNDAY_EVENING, "dev-a")
        _store(hymn, datetime(2026, 8, 16, 19, 30, tzinfo=SAO_PAULO), "dev-a")

        resp = self.client.get(f"{TOP_HYMNS_URL}?from=2026-08-09&to=2026-08-09")

        assert resp.data["hymns"][0]["occurrence_count"] == 1

    def test_empty_history_returns_an_empty_list(self) -> None:
        resp = self.client.get(TOP_HYMNS_URL)
        assert resp.data["hymns"] == []


@pytest.mark.django_db
class TestPanelRoles:
    """The hymnal report is readable by every panel role (specs/012-feature-role-permissions)."""

    @pytest.mark.parametrize("role", [Role.ADMIN, Role.LEADER, Role.MEDIA])
    @pytest.mark.parametrize("url", [OCCURRENCES_URL, TOP_HYMNS_URL])
    def test_role_reads_report(self, role: Role, url: str) -> None:
        client, _ = make_role_client(role)
        assert client.get(url).status_code == 200
