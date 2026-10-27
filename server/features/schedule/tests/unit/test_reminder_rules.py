"""Pure rules of the rota reminders (specs/024-schedule-reminders research R-04–R-06)."""

import json
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from features.schedule.reminder_dtos import ReminderClaimKey, RotaEntryDTO
from features.schedule.services.reminder_rules import (
    OVERWRITE_WINDOW,
    eve_date,
    eve_occasion,
    group_by_claim,
    is_past_overwrite_window,
    month_occasion,
    publishing_first_saves,
    slots_json,
    week_occasion,
    week_range,
)

SP = ZoneInfo("America/Sao_Paulo")
MONDAY = date(2026, 10, 26)


def _at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=SP)


def _entry(
    day: date, member_id: int = 7, service_id: int = 3, start: time = time(19, 30)
) -> RotaEntryDTO:
    return RotaEntryDTO(
        date=day,
        member_id=member_id,
        service_id=service_id,
        service_name=f"Culto {service_id}",
        start_time=start,
        month_first_saved_at=datetime(2026, 10, 1, 9, 0, tzinfo=SP),
    )


class TestWeekRange:
    def test_monday_from_eight(self) -> None:
        assert week_range(_at(MONDAY, 8, 0)) == (MONDAY, date(2026, 11, 1))
        assert week_range(_at(MONDAY, 23, 59)) == (MONDAY, date(2026, 11, 1))

    def test_monday_before_eight(self) -> None:
        assert week_range(_at(MONDAY, 7, 59)) is None

    def test_other_days(self) -> None:
        assert week_range(_at(date(2026, 10, 27), 8, 0)) is None


class TestEveDate:
    def test_from_seven_pm_is_tomorrow(self) -> None:
        assert eve_date(_at(date(2026, 10, 28), 19, 0)) == date(2026, 10, 29)

    def test_before_seven_pm_is_none(self) -> None:
        assert eve_date(_at(date(2026, 10, 28), 18, 59)) is None

    def test_after_midnight_is_none(self) -> None:
        # The eve of Thursday is gone once Thursday has started (FR-007).
        assert eve_date(_at(date(2026, 10, 29), 0, 10)) is None

    def test_crosses_month_end(self) -> None:
        assert eve_date(_at(date(2026, 10, 31), 20, 0)) == date(2026, 11, 1)


class TestPublication:
    def test_range_is_today_minus_the_window(self) -> None:
        since, until = publishing_first_saves(_at(date(2026, 11, 1), 10, 31))
        assert since == _at(date(2026, 11, 1), 0, 0) - OVERWRITE_WINDOW
        assert until == _at(date(2026, 11, 1), 10, 1)

    def test_past_overwrite_window(self) -> None:
        saved = _at(date(2026, 11, 1), 10, 0)
        assert not is_past_overwrite_window(saved, _at(date(2026, 11, 1), 10, 29))
        assert is_past_overwrite_window(saved, _at(date(2026, 11, 1), 10, 30))


class TestOccasions:
    def test_keys(self) -> None:
        assert week_occasion(MONDAY) == "2026-10-26"
        assert eve_occasion(_entry(date(2026, 10, 29))) == "2026-10-29/3"
        assert month_occasion(2026, 1) == "2026-01"


class TestGroupAndSlots:
    def test_groups_per_member_ordered(self) -> None:
        sunday, tuesday = _entry(date(2026, 11, 1)), _entry(date(2026, 10, 27))
        other = _entry(date(2026, 10, 29), member_id=9)
        groups = group_by_claim([sunday, other, tuesday], lambda _: "w")
        assert groups == {
            ReminderClaimKey(member_id=7, occasion="w"): [tuesday, sunday],
            ReminderClaimKey(member_id=9, occasion="w"): [other],
        }

    def test_slots_json_shape(self) -> None:
        later = _entry(date(2026, 10, 29), service_id=5, start=time(19, 30))
        earlier = _entry(date(2026, 10, 29), service_id=1, start=time(9, 0))
        raw = slots_json([later, earlier])
        assert json.loads(raw) == [
            {"date": "2026-10-29", "service": "Culto 1", "time": "09:00"},
            {"date": "2026-10-29", "service": "Culto 5", "time": "19:30"},
        ]
        assert " " not in raw.replace("Culto ", "")

    def test_slots_keep_accents(self) -> None:
        entry = _entry(date(2026, 10, 27)).model_copy(update={"service_name": "Terça de Oração"})
        assert "Terça de Oração" in slots_json([entry])
