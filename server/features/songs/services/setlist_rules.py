"""Pure rules of the Sunday setlist (specs/017-sunday-setlist-push). No Django, no I/O."""

from collections import Counter
from collections.abc import Iterable
from datetime import date, datetime, time

from core.domain.exceptions import DuplicateSetlistPositionError, SetlistDateNotSundayError
from features.songs.setlist_dtos import SetlistItemInput

_SUNDAY = 6  # date.weekday(): Monday 0 ... Sunday 6
REMINDER_START = time(21, 0)
REMINDER_STEP_MINUTES = 30


def ensure_sunday(day: date) -> None:
    """>>> ensure_sunday(date(2026, 10, 4))"""
    if day.weekday() != _SUNDAY:
        raise SetlistDateNotSundayError(day)


def ensure_unique_positions(items: Iterable[SetlistItemInput]) -> None:
    """>>> ensure_unique_positions([SetlistItemInput(song_id=1, position=1, tone="G")])"""
    counts = Counter(item.position for item in items)
    repeated = [position for position, count in counts.items() if count > 1]
    if repeated:
        raise DuplicateSetlistPositionError(repeated)


def current_reminder_slot(now_local: datetime) -> datetime | None:
    """Start of the reminder window ``now_local`` falls in, or ``None`` outside Sunday
    21:00-24:00. Only the current window is ever computed, so a window missed while the job was
    down is never sent late (spec 017 FR-019).

    >>> current_reminder_slot(datetime(2026, 10, 4, 22, 47, tzinfo=SAO_PAULO))
    datetime.datetime(2026, 10, 4, 22, 30, tzinfo=...)
    """
    if now_local.weekday() != _SUNDAY or now_local.time() < REMINDER_START:
        return None
    minute = now_local.minute - now_local.minute % REMINDER_STEP_MINUTES
    return now_local.replace(minute=minute, second=0, microsecond=0)
