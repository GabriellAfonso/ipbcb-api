from datetime import date, datetime, timezone

import pytest

from core.domain.exceptions import EventDatesInvalidError, EventStatusFilterError
from features.events.domain.event_dates import (
    ensure_dates_ordered,
    is_active,
    last_day,
    today_in_events_zone,
)
from features.events.domain.event_enums import EventStatusFilter, parse_status_filter

NOV_14 = date(2026, 11, 14)
NOV_16 = date(2026, 11, 16)


class TestTodayInEventsZone:
    def test_early_utc_morning_is_still_the_previous_day_in_sao_paulo(self) -> None:
        assert today_in_events_zone(datetime(2026, 11, 15, 2, 30, tzinfo=timezone.utc)) == NOV_14

    def test_after_midnight_in_sao_paulo_is_the_next_day(self) -> None:
        assert today_in_events_zone(datetime(2026, 11, 15, 3, 0, tzinfo=timezone.utc)) == date(
            2026, 11, 15
        )


class TestLastDayAndActive:
    def test_last_day_is_end_date_when_present(self) -> None:
        assert last_day(NOV_14, NOV_16) == NOV_16

    def test_last_day_is_start_date_for_a_one_day_event(self) -> None:
        assert last_day(NOV_14, None) == NOV_14

    @pytest.mark.parametrize(
        ("today", "expected"),
        [(date(2026, 11, 13), True), (NOV_16, True), (date(2026, 11, 17), False)],
    )
    def test_active_until_the_end_of_the_last_day(self, today: date, expected: bool) -> None:
        assert is_active(NOV_14, NOV_16, today) is expected


class TestEnsureDatesOrdered:
    @pytest.mark.parametrize("end", [None, NOV_14, NOV_16])
    def test_accepts_absent_same_or_later_end(self, end: date | None) -> None:
        ensure_dates_ordered(NOV_14, end)

    def test_refuses_end_before_start(self) -> None:
        with pytest.raises(EventDatesInvalidError):
            ensure_dates_ordered(NOV_16, NOV_14)


class TestParseStatusFilter:
    def test_absent_means_all(self) -> None:
        assert parse_status_filter(None) is EventStatusFilter.ALL

    @pytest.mark.parametrize("raw", ["active", "past", "all"])
    def test_known_values(self, raw: str) -> None:
        assert parse_status_filter(raw).value == raw

    @pytest.mark.parametrize("raw", ["old", "", "ACTIVE"])
    def test_unknown_value_is_refused(self, raw: str) -> None:
        with pytest.raises(EventStatusFilterError):
            parse_status_filter(raw)
