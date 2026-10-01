from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from core.domain.exceptions import DuplicateSetlistPositionError, SetlistDateNotSundayError
from features.songs.services.setlist_rules import (
    current_reminder_slot,
    ensure_sunday,
    ensure_unique_positions,
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


class TestCurrentReminderSlot:
    @pytest.mark.parametrize(
        ("hour", "minute", "slot"),
        [(21, 0, (21, 0)), (21, 29, (21, 0)), (21, 30, (21, 30)), (23, 59, (23, 30))],
    )
    def test_sunday_night_rounds_down_to_the_half_hour(
        self, hour: int, minute: int, slot: tuple[int, int]
    ) -> None:
        result = current_reminder_slot(_at(4, hour, minute))
        assert result == datetime(2026, 10, 4, slot[0], slot[1], tzinfo=SP)

    def test_before_nine_is_outside(self) -> None:
        assert current_reminder_slot(_at(4, 20, 59)) is None

    def test_saturday_night_is_outside(self) -> None:
        assert current_reminder_slot(_at(3, 22, 0)) is None

    def test_keeps_the_local_timezone(self) -> None:
        result = current_reminder_slot(_at(4, 22, 10))
        assert result is not None and result.tzinfo is SP
