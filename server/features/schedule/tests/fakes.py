"""Named test doubles for the rota reminders (specs/024-schedule-reminders), per CLAUDE.md §10."""

from collections.abc import Collection
from datetime import date, datetime
from uuid import UUID

from features.schedule.reminder_dtos import ReminderClaimKey, ReminderKind, RotaEntryDTO


class FixedClock:
    """Clock that always returns the same instant. Own copy: features never import each other."""

    def __init__(self, moment: datetime) -> None:
        self.moment = moment

    def now(self) -> datetime:
        return self.moment


class FakeRotaReminderRepository:
    """In-memory ``RotaReminderRepository``. ``entries`` carry their month's first save already,
    as the real query annotates it; ``claims`` persists across runs like the table.

    >>> FakeRotaReminderRepository([entry]).entries_between(entry.date, entry.date)
    [entry]
    """

    def __init__(self, entries: list[RotaEntryDTO] | None = None) -> None:
        self.entries = list(entries or [])
        self.claims: set[tuple[ReminderKind, ReminderClaimKey]] = set()

    def entries_between(self, first: date, last: date) -> list[RotaEntryDTO]:
        return [e for e in self.entries if first <= e.date <= last]

    def entries_of_months_from(
        self, months: Collection[tuple[int, int]], first: date
    ) -> list[RotaEntryDTO]:
        wanted = set(months)
        return [
            e for e in self.entries if (e.date.year, e.date.month) in wanted and e.date >= first
        ]

    def months_first_saved_between(self, since: datetime, until: datetime) -> list[tuple[int, int]]:
        months = {
            (e.date.year, e.date.month)
            for e in self.entries
            if since <= e.month_first_saved_at <= until
        }
        return sorted(months)

    def claim(
        self, kind: ReminderKind, keys: Collection[ReminderClaimKey], run_id: UUID
    ) -> set[ReminderClaimKey]:
        won = {key for key in keys if (kind, key) not in self.claims}
        self.claims |= {(kind, key) for key in won}
        return won
