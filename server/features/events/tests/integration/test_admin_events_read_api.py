"""US5 — the panel reviews every event, past included (specs/020-church-events)."""

from datetime import date, time

import pytest
from rest_framework.test import APIClient

from conftest import make_member_client, make_role_client
from core.domain.access import Role
from features.events.domain.event_enums import EventVisibility
from features.events.models.event import Event
from features.events.tests.integration.conftest import ADMIN_URL, MakeEvent, admin_detail_url

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("clock")]


def _client() -> APIClient:
    client, _ = make_role_client(Role.LEADER, username="lideranca")
    return client


def _ids(client: APIClient, query: str = "") -> list[int]:
    response = client.get(f"{ADMIN_URL}{query}")
    assert response.status_code == 200
    return [event["id"] for event in response.data["events"]]


@pytest.fixture
def seeded(make_event: MakeEvent) -> dict[str, Event]:
    return {
        "past_members": make_event(
            start_date=date(2026, 11, 1), visibility=EventVisibility.MEMBERS
        ),
        "today_timed": make_event(start_date=date(2026, 11, 14), start_time=time(19, 0)),
        "today_all_day": make_event(start_date=date(2026, 11, 14)),
        "future": make_event(start_date=date(2026, 12, 1), visibility=EventVisibility.MEMBERS),
    }


def test_default_is_every_event_newest_first(seeded: dict[str, Event]) -> None:
    order = ["future", "today_timed", "today_all_day", "past_members"]
    client = _client()

    assert _ids(client) == [seeded[name].pk for name in order]
    assert _ids(client, "?status=all") == _ids(client)


@pytest.mark.parametrize(
    ("status", "names"),
    [("active", ["future", "today_timed", "today_all_day"]), ("past", ["past_members"])],
)
def test_status_filter(seeded: dict[str, Event], status: str, names: list[str]) -> None:
    assert _ids(_client(), f"?status={status}") == [seeded[name].pk for name in names]


def test_unknown_status_is_400_naming_it() -> None:
    response = _client().get(f"{ADMIN_URL}?status=old")

    assert response.status_code == 400
    assert "'old'" in response.data["field_errors"]["status"][0]


def test_detail_shows_past_members_event_to_a_non_member_manager(
    seeded: dict[str, Event],
) -> None:
    response = _client().get(admin_detail_url(seeded["past_members"].pk))

    assert response.status_code == 200
    assert response.data["visibility"] == "members"
    assert set(response.data) >= {"created_by", "updated_by", "created_at", "updated_at"}


def test_responses_are_private(seeded: dict[str, Event]) -> None:
    assert _client().get(ADMIN_URL)["Cache-Control"] == "private, no-store"


@pytest.mark.parametrize("url", [ADMIN_URL, admin_detail_url(1)])
def test_member_without_role_is_refused(url: str) -> None:
    client, _ = make_member_client()

    assert client.get(url).status_code == 403
