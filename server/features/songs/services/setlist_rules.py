"""Pure rules of the Sunday setlist (specs/017-sunday-setlist-push). No Django, no I/O."""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from core.domain.exceptions import DuplicateSetlistPositionError, SetlistDateNotSundayError
from features.songs.setlist_dtos import SetlistItemInput

_MONDAY = 0  # date.weekday(): Monday 0 ... Sunday 6
_SUNDAY = 6
SUNDAY_REMINDER_START = time(21, 0)
SUNDAY_REMINDER_STEP_MINUTES = 30
# Monday is a catch-up for a Sunday nobody registered: no night windows, and a wider step so a
# forgotten Sunday does not turn into a stream of pushes the user ends up silencing.
MONDAY_REMINDER_START = time(8, 0)
MONDAY_REMINDER_STEP_MINUTES = 120
# A setlist serves one Sunday; ``Played`` is the lasting record (spec 017 FR-028). Unconfirmed
# ones live longer so the pending card has time to be worked through before they go.
CONFIRMED_RETENTION_DAYS = 30
UNCONFIRMED_RETENTION_DAYS = 90


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


@dataclass(frozen=True)
class ReminderWindow:
    """The window a reminder run falls in: which Sunday's setlist it is about, and when the
    window started. Monday windows belong to the previous day's setlist."""

    setlist_date: date
    start: datetime


def current_reminder_window(now_local: datetime) -> ReminderWindow | None:
    """The reminder window ``now_local`` falls in, or ``None`` outside Sunday 21:00-24:00
    (half-hour windows) and Monday 08:00-24:00 (two-hour windows). Only the current window is
    ever computed, so a window missed while the job was down is never sent late (spec 017
    FR-019).

    >>> current_reminder_window(datetime(2026, 10, 4, 22, 47, tzinfo=SAO_PAULO)).start
    datetime.datetime(2026, 10, 4, 22, 30, tzinfo=...)
    >>> current_reminder_window(datetime(2026, 10, 5, 9, 15, tzinfo=SAO_PAULO)).setlist_date
    datetime.date(2026, 10, 4)
    """
    weekday = now_local.weekday()
    if weekday == _SUNDAY and now_local.time() >= SUNDAY_REMINDER_START:
        start = _window_start(now_local, SUNDAY_REMINDER_START, SUNDAY_REMINDER_STEP_MINUTES)
        return ReminderWindow(setlist_date=now_local.date(), start=start)
    if weekday == _MONDAY and now_local.time() >= MONDAY_REMINDER_START:
        start = _window_start(now_local, MONDAY_REMINDER_START, MONDAY_REMINDER_STEP_MINUTES)
        return ReminderWindow(setlist_date=now_local.date() - timedelta(days=1), start=start)
    return None


def _window_start(now_local: datetime, first: time, step_minutes: int) -> datetime:
    first_start = now_local.replace(hour=first.hour, minute=first.minute, second=0, microsecond=0)
    elapsed = int((now_local - first_start).total_seconds() // 60)
    return first_start + timedelta(minutes=elapsed - elapsed % step_minutes)


def purge_cutoffs(today: date) -> tuple[date, date]:
    """``(confirmed_before, unconfirmed_before)``: setlists dated strictly before each cutoff
    are expired, the first for those with plays registered, the second for those without.

    >>> purge_cutoffs(date(2026, 12, 31))
    (datetime.date(2026, 12, 1), datetime.date(2026, 10, 2))
    """
    confirmed_before = today - timedelta(days=CONFIRMED_RETENTION_DAYS)
    unconfirmed_before = today - timedelta(days=UNCONFIRMED_RETENTION_DAYS)
    return confirmed_before, unconfirmed_before
