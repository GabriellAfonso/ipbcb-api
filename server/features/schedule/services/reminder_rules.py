"""Pure rules of the rota reminders (specs/024-schedule-reminders). No Django, no I/O.

Every window ends at midnight and only the current one is computed, so an occasion missed while
the job was down is sent later the same day and never on a later day (spec FR-014, research R-05).
"""

import json
from collections import defaultdict
from collections.abc import Callable, Iterable
from datetime import date, datetime, time, timedelta

from features.schedule.reminder_dtos import ReminderClaimKey, RotaEntryDTO, RotaSlot

# How long after its first save a month may still be replaced. Shared by the 409 rule in
# ScheduleService and by the reminders, which wait for it so they never announce a rota that can
# still change (spec FR-010, FR-019).
OVERWRITE_WINDOW = timedelta(minutes=30)
WEEK_SUMMARY_START = time(8, 0)
EVE_REMINDER_START = time(19, 0)
_MONDAY = 0  # date.weekday()
_DAYS_IN_WEEK = 7


def week_range(now_local: datetime) -> tuple[date, date] | None:
    """Monday to Sunday of this week, from Monday 08:00 until midnight; ``None`` otherwise.

    >>> week_range(datetime(2026, 10, 26, 8, 3, tzinfo=SAO_PAULO))
    (datetime.date(2026, 10, 26), datetime.date(2026, 11, 1))
    """
    if now_local.weekday() != _MONDAY or now_local.time() < WEEK_SUMMARY_START:
        return None
    monday = now_local.date()
    return monday, monday + timedelta(days=_DAYS_IN_WEEK - 1)


def eve_date(now_local: datetime) -> date | None:
    """The date whose entries get their eve reminder now: tomorrow, from 19:00 until midnight.

    >>> eve_date(datetime(2026, 10, 28, 19, 5, tzinfo=SAO_PAULO))
    datetime.date(2026, 10, 29)
    """
    if now_local.time() < EVE_REMINDER_START:
        return None
    return now_local.date() + timedelta(days=1)


def publishing_first_saves(now_local: datetime) -> tuple[datetime, datetime]:
    """``(since, until)``, both inclusive: a month whose first save falls in that range has its
    publication moment (first save + window) today and already past (spec FR-009, FR-012).

    >>> publishing_first_saves(datetime(2026, 11, 1, 10, 31, tzinfo=SAO_PAULO))
    (datetime(2026, 10, 31, 23, 30, ...), datetime(2026, 11, 1, 10, 1, ...))
    """
    start_of_today = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_of_today - OVERWRITE_WINDOW, now_local - OVERWRITE_WINDOW


def is_past_overwrite_window(first_saved_at: datetime, now: datetime) -> bool:
    """>>> is_past_overwrite_window(datetime(2026, 11, 1, 10, 0, tzinfo=UTC), ten_thirty_utc)
    True
    """
    return first_saved_at + OVERWRITE_WINDOW <= now


def week_occasion(monday: date) -> str:
    """>>> week_occasion(date(2026, 10, 26))
    '2026-10-26'
    """
    return monday.isoformat()


def eve_occasion(entry: RotaEntryDTO) -> str:
    """Date and service, the rota's own unique key: row ids change on every save (R-01).

    >>> eve_occasion(entry_on_thursday_service_3)
    '2026-10-29/3'
    """
    return f"{entry.date.isoformat()}/{entry.service_id}"


def month_occasion(year: int, month: int) -> str:
    """>>> month_occasion(2026, 11)
    '2026-11'
    """
    return f"{year:04d}-{month:02d}"


def group_by_claim(
    entries: Iterable[RotaEntryDTO], occasion_of: Callable[[RotaEntryDTO], str]
) -> dict[ReminderClaimKey, list[RotaEntryDTO]]:
    """Entries per (member, occasion), each list ordered by date then start time.

    >>> group_by_claim([tue, sun], lambda e: "2026-10-26")
    {ReminderClaimKey(member_id=7, occasion='2026-10-26'): [tue, sun]}
    """
    groups: dict[ReminderClaimKey, list[RotaEntryDTO]] = defaultdict(list)
    for entry in sorted(entries, key=lambda e: (e.date, e.start_time)):
        groups[ReminderClaimKey(member_id=entry.member_id, occasion=occasion_of(entry))].append(
            entry
        )
    return dict(groups)


def slots_json(entries: Iterable[RotaEntryDTO]) -> str:
    """The ``slots`` push value: a compact JSON array, by date then time (contract R-06).

    >>> slots_json([thursday_entry])
    '[{"date":"2026-10-29","service":"Quinta de Oração","time":"19:30"}]'
    """
    ordered = sorted(entries, key=lambda e: (e.date, e.start_time))
    slots = [_slot(entry).model_dump() for entry in ordered]
    return json.dumps(slots, ensure_ascii=False, separators=(",", ":"))


def _slot(entry: RotaEntryDTO) -> RotaSlot:
    return RotaSlot(
        date=entry.date.isoformat(),
        service=entry.service_name,
        time=entry.start_time.strftime("%H:%M"),
    )
