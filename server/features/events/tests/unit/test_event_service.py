from datetime import date, datetime, time, timezone

import pytest

from core.domain.exceptions import EventNotFoundError, EventStatusFilterError
from features.events.domain.event_enums import EventVisibility
from features.events.services.event_service import EventService
from features.events.tests.fakes import FakeEventImageStorage, FakeEventRepository, FixedClock

# 2026-11-14 12:00 in São Paulo (UTC-3).
NOON_NOV_14 = datetime(2026, 11, 14, 15, 0, tzinfo=timezone.utc)


def _service(repository: FakeEventRepository, now: datetime = NOON_NOV_14) -> EventService:
    return EventService(
        repository=repository, image_storage=FakeEventImageStorage(), clock=FixedClock(now)
    )


class TestListVisible:
    def test_ongoing_then_future_in_order_and_no_past(self) -> None:
        repo = FakeEventRepository()
        timed = repo.add(start_date=date(2026, 11, 17), start_time=time(19, 30))
        all_day = repo.add(start_date=date(2026, 11, 17))
        ongoing = repo.add(start_date=date(2026, 11, 13), end_date=date(2026, 11, 15))
        repo.add(start_date=date(2026, 11, 7))

        listed = _service(repo).list_visible(include_members=False)

        assert [r.id for r in listed] == [ongoing.id, all_day.id, timed.id]

    def test_members_events_only_when_asked(self) -> None:
        repo = FakeEventRepository()
        members = repo.add(visibility=EventVisibility.MEMBERS)

        assert _service(repo).list_visible(include_members=False) == []
        assert _service(repo).list_visible(include_members=True) == [members]

    @pytest.mark.parametrize(
        ("now", "listed"),
        [
            (datetime(2026, 11, 15, 2, 59, tzinfo=timezone.utc), True),  # 23:59 in São Paulo
            (datetime(2026, 11, 15, 3, 0, tzinfo=timezone.utc), False),  # 00:00 next day
        ],
    )
    def test_one_day_event_leaves_at_midnight_sao_paulo(self, now: datetime, listed: bool) -> None:
        repo = FakeEventRepository()
        repo.add(start_date=date(2026, 11, 14))

        assert bool(_service(repo, now).list_visible(include_members=False)) is listed


class TestGetVisible:
    def test_returns_an_active_visible_event(self) -> None:
        repo = FakeEventRepository()
        event = repo.add()

        assert _service(repo).get_visible(event.id, include_members=False) == event

    @pytest.mark.parametrize(
        "fields",
        [{"start_date": date(2026, 11, 1)}, {"visibility": EventVisibility.MEMBERS}],
    )
    def test_past_or_hidden_is_not_found(self, fields: dict[str, object]) -> None:
        repo = FakeEventRepository()
        event = repo.add(**fields)

        with pytest.raises(EventNotFoundError):
            _service(repo).get_visible(event.id, include_members=False)

    def test_missing_is_not_found(self) -> None:
        with pytest.raises(EventNotFoundError):
            _service(FakeEventRepository()).get_visible(99, include_members=True)


class TestManagement:
    def _seeded(self) -> tuple[FakeEventRepository, int, int]:
        repo = FakeEventRepository()
        past = repo.add(start_date=date(2026, 11, 1), visibility=EventVisibility.MEMBERS)
        future = repo.add(start_date=date(2026, 12, 1))
        return repo, past.id, future.id

    @pytest.mark.parametrize(
        ("status", "expected_index"),
        [(None, [1, 0]), ("all", [1, 0]), ("active", [1]), ("past", [0])],
    )
    def test_status_filter_newest_first(
        self, status: str | None, expected_index: list[int]
    ) -> None:
        repo, past_id, future_id = self._seeded()
        ids = [past_id, future_id]

        listed = _service(repo).list_for_management(status)

        assert [r.id for r in listed] == [ids[i] for i in expected_index]

    def test_unknown_status_is_refused(self) -> None:
        with pytest.raises(EventStatusFilterError):
            _service(FakeEventRepository()).list_for_management("old")

    def test_detail_ignores_state_and_visibility(self) -> None:
        repo, past_id, _ = self._seeded()

        assert _service(repo).get_for_management(past_id).id == past_id

    def test_detail_of_missing_is_not_found(self) -> None:
        with pytest.raises(EventNotFoundError):
            _service(FakeEventRepository()).get_for_management(99)


def test_image_url_path_comes_from_storage() -> None:
    assert _service(FakeEventRepository()).image_url_path("events/a.jpg") == "/media/events/a.jpg"
