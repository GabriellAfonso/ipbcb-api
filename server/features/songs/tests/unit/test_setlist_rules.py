from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from core.domain.exceptions import DuplicateSetlistPositionError, SetlistDateNotSundayError
from features.songs.services.setlist_rules import (
    ReminderWindow,
    current_reminder_window,
    ensure_sunday,
    ensure_unique_positions,
    purge_cutoffs,
)
from features.songs.setlist_dtos import SetlistItemInput

SP = ZoneInfo("America/Sao_Paulo")


def _items(*positions: int) -> list[SetlistItemInput]:
    return [SetlistItemInput(song_id=1, position=p, tone="G") for p in positions]


class TestEnsureSunday:
    def test_sunday_passes(self) -> None:
        ensure_sunday(date(2026, 10, 4))

    def test_monday_is_refused_naming_it(self) -> None:
        with pytest.raises(SetlistDateNotSundayError, match=r"2026-10-05 \(Monday\)"):
            ensure_sunday(date(2026, 10, 5))


class TestEnsureUniquePositions:
    def test_unique_passes(self) -> None:
        ensure_unique_positions(_items(1, 2, 3))

    def test_repeats_are_named(self) -> None:
        with pytest.raises(DuplicateSetlistPositionError, match=r"\[2, 3\]"):
            ensure_unique_positions(_items(1, 2, 2, 3, 3))


def _at(day: int, hour: int, minute: int) -> datetime:
    return datetime(2026, 10, day, hour, minute, 17, tzinfo=SP)


class TestCurrentReminderWindow:
    @pytest.mark.parametrize(
        ("hour", "minute", "slot"),
        [(21, 0, (21, 0)), (21, 29, (21, 0)), (21, 30, (21, 30)), (23, 59, (23, 30))],
    )
    def test_sunday_night_rounds_down_to_the_half_hour(
        self, hour: int, minute: int, slot: tuple[int, int]
    ) -> None:
        result = current_reminder_window(_at(4, hour, minute))
        assert result == ReminderWindow(date(2026, 10, 4), datetime(2026, 10, 4, *slot, tzinfo=SP))

    @pytest.mark.parametrize(
        ("hour", "minute", "slot_hour"),
        [(8, 0, 8), (9, 59, 8), (10, 0, 10), (15, 30, 14), (22, 0, 22), (23, 59, 22)],
    )
    def test_monday_rounds_down_to_two_hours_for_the_previous_sunday(
        self, hour: int, minute: int, slot_hour: int
    ) -> None:
        result = current_reminder_window(_at(5, hour, minute))
        monday_slot = datetime(2026, 10, 5, slot_hour, 0, tzinfo=SP)
        assert result == ReminderWindow(date(2026, 10, 4), monday_slot)

    def test_before_nine_is_outside(self) -> None:
        assert current_reminder_window(_at(4, 20, 59)) is None

    def test_monday_night_before_eight_is_outside(self) -> None:
        assert current_reminder_window(_at(5, 0, 0)) is None
        assert current_reminder_window(_at(5, 7, 59)) is None

    def test_saturday_night_is_outside(self) -> None:
        assert current_reminder_window(_at(3, 22, 0)) is None

    def test_tuesday_is_outside(self) -> None:
        assert current_reminder_window(_at(6, 10, 0)) is None

    def test_keeps_the_local_timezone(self) -> None:
        result = current_reminder_window(_at(4, 22, 10))
        assert result is not None and result.start.tzinfo is SP


def test_purge_cutoffs_are_30_and_90_days_back() -> None:
    assert purge_cutoffs(date(2026, 12, 31)) == (date(2026, 12, 1), date(2026, 10, 2))
