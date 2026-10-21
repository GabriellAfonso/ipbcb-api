"""Dates of an event and the active window (specs/020-church-events, Definitions).

An event is active until the end of its last day in São Paulo. Nothing about it is stored: the
service computes "today" from the injected clock on every request, so no job is needed.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from core.domain.exceptions import EventDatesInvalidError

# Explicit, not settings.TIME_ZONE: the rule is the church's local day, whatever the server says.
EVENTS_TIME_ZONE = ZoneInfo("America/Sao_Paulo")


def today_in_events_zone(now: datetime) -> date:
    """The calendar date of ``now`` in São Paulo. ``now`` must be timezone-aware.

    >>> today_in_events_zone(datetime(2026, 11, 15, 2, 30, tzinfo=timezone.utc))
    datetime.date(2026, 11, 14)
    """
    return now.astimezone(EVENTS_TIME_ZONE).date()


def last_day(start_date: date, end_date: date | None) -> date:
    """The day the event ends: ``end_date``, or ``start_date`` for a one-day event.

    >>> last_day(date(2026, 11, 14), None)
    datetime.date(2026, 11, 14)
    """
    return end_date or start_date


def is_active(start_date: date, end_date: date | None, today: date) -> bool:
    """Whether the event is still active on ``today``.

    >>> is_active(date(2026, 11, 14), date(2026, 11, 16), date(2026, 11, 16))
    True
    """
    return last_day(start_date, end_date) >= today


def ensure_dates_ordered(start_date: date, end_date: date | None) -> None:
    """Refuse an ``end_date`` before ``start_date``.

    >>> ensure_dates_ordered(date(2026, 11, 14), date(2026, 11, 16))
    """
    if end_date is not None and end_date < start_date:
        raise EventDatesInvalidError(start_date, end_date)
