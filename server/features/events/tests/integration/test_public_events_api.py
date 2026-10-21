"""US1 — anyone sees upcoming events (specs/020-church-events)."""

from datetime import date, datetime, time, timedelta, timezone

import pytest
from rest_framework.test import APIClient

from features.events.tests.fakes import FixedClock
from features.events.tests.integration.conftest import (
    PUBLIC_URL,
    TODAY,
    MakeEvent,
    public_detail_url,
)

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("clock")]


def test_anonymous_list_has_ongoing_then_future_and_no_past(make_event: MakeEvent) -> None:
    ongoing = make_event(start_date=TODAY - timedelta(days=1), end_date=TODAY + timedelta(days=1))
    timed = make_event(start_date=TODAY + timedelta(days=3), start_time=time(19, 30))
    all_day = make_event(start_date=TODAY + timedelta(days=3))
    make_event(start_date=TODAY - timedelta(days=7))

    response = APIClient().get(PUBLIC_URL)

    assert response.status_code == 200
    assert [event["id"] for event in response.data] == [ongoing.pk, all_day.pk, timed.pk]


def test_resource_shape(make_event: MakeEvent) -> None:
    event = make_event(start_time=time(19, 30), title="Congresso de Jovens")

    body = APIClient().get(public_detail_url(event.pk)).data

    assert body == {
        "id": event.pk,
        "title": "Congresso de Jovens",
        "start_date": TODAY.isoformat(),
        "end_date": None,
        "start_time": "19:30",
        "location": None,
        "description": None,
        "image_url": f"http://testserver/ipbcb/media/{event.image_path}",
        "visibility": "public",
    }


@pytest.mark.parametrize(
    ("now", "listed"),
    [
        (datetime(2026, 11, 15, 2, 59, tzinfo=timezone.utc), True),  # 23:59 in São Paulo
        (datetime(2026, 11, 15, 3, 0, tzinfo=timezone.utc), False),  # 00:00 the next day
    ],
)
def test_one_day_event_leaves_at_midnight_sao_paulo(
    make_event: MakeEvent, clock: FixedClock, now: datetime, listed: bool
) -> None:
    make_event(start_date=TODAY)
    clock.now_value = now

    assert bool(APIClient().get(PUBLIC_URL).data) is listed


def test_past_event_detail_is_404(make_event: MakeEvent) -> None:
    event = make_event(start_date=date(2026, 11, 1))

    response = APIClient().get(public_detail_url(event.pk))

    assert response.status_code == 404
    assert response.data["error_code"] == "NOT_FOUND"


def test_no_active_events_is_an_empty_list(make_event: MakeEvent) -> None:
    make_event(start_date=date(2026, 1, 1))

    assert APIClient().get(PUBLIC_URL).data == []


def test_responses_are_private_with_etag(make_event: MakeEvent) -> None:
    make_event()

    first = APIClient().get(PUBLIC_URL)
    again = APIClient().get(PUBLIC_URL, HTTP_IF_NONE_MATCH=first["ETag"])

    assert first["Cache-Control"] == "private, no-store"
    assert "Authorization" in first["Vary"]
    assert again.status_code == 304
