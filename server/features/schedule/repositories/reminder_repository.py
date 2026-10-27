from collections.abc import Collection
from datetime import date, datetime
from uuid import UUID

from django.db.models import Min, OuterRef, Q, QuerySet, Subquery

from features.schedule.models import MonthlySchedule, ScheduleReminderClaim
from features.schedule.reminder_dtos import ReminderClaimKey, ReminderKind, RotaEntryDTO


class RotaReminderRepositoryImpl:
    """Reads and claims of the rota reminders (specs/024-schedule-reminders R-01, R-02, R-04)."""

    def entries_between(self, first: date, last: date) -> list[RotaEntryDTO]:
        """>>> RotaReminderRepositoryImpl().entries_between(date(2026, 10, 26), date(2026, 11, 1))
        [RotaEntryDTO(date=datetime.date(2026, 10, 27), ...)]
        """
        return _to_dtos(_entries().filter(date__range=(first, last)))

    def entries_of_months_from(
        self, months: Collection[tuple[int, int]], first: date
    ) -> list[RotaEntryDTO]:
        """Entries of any of ``months`` dated ``first`` or later, in one query.

        >>> RotaReminderRepositoryImpl().entries_of_months_from({(2026, 11)}, date(2026, 11, 1))
        [RotaEntryDTO(...)]
        """
        if not months:
            return []
        in_months = Q()
        for year, month in months:
            in_months |= Q(year=year, month=month)
        return _to_dtos(_entries().filter(in_months, date__gte=first))

    def months_first_saved_between(self, since: datetime, until: datetime) -> list[tuple[int, int]]:
        """``(year, month)`` of every month whose earliest save falls in ``[since, until]``.

        >>> RotaReminderRepositoryImpl().months_first_saved_between(since, until)
        [(2026, 11)]
        """
        rows = (
            MonthlySchedule.objects.values("year", "month")
            .annotate(first_saved=Min("created_at"))
            .filter(first_saved__gte=since, first_saved__lte=until)
            .order_by("year", "month")
            .values_list("year", "month")
        )
        return [(year, month) for year, month in rows]

    def claim(
        self, kind: ReminderKind, keys: Collection[ReminderClaimKey], run_id: UUID
    ) -> set[ReminderClaimKey]:
        """Insert every claim at once and return the ones this run won. ``ignore_conflicts``
        does not say which rows went in, so the run id tells them apart (R-02).

        >>> RotaReminderRepositoryImpl().claim(ReminderKind.EVE, {key}, uuid4())
        {ReminderClaimKey(member_id=7, occasion='2026-10-29/3')}
        """
        if not keys:
            return set()
        rows = [
            ScheduleReminderClaim(
                kind=kind.value, member_id=key.member_id, occasion=key.occasion, run_id=run_id
            )
            for key in keys
        ]
        ScheduleReminderClaim.objects.bulk_create(rows, ignore_conflicts=True)
        won = ScheduleReminderClaim.objects.filter(kind=kind.value, run_id=run_id).values_list(
            "member_id", "occasion"
        )
        return {ReminderClaimKey(member_id=member_id, occasion=occ) for member_id, occ in won}


def _entries() -> QuerySet[MonthlySchedule]:
    first_save = (
        MonthlySchedule.objects.filter(year=OuterRef("year"), month=OuterRef("month"))
        .order_by("created_at")
        .values("created_at")[:1]
    )
    return (
        MonthlySchedule.objects.select_related("schedule_type", "member")
        .annotate(month_first_saved_at=Subquery(first_save))
        .order_by("date", "schedule_type__start_time")
    )


def _to_dtos(rows: QuerySet[MonthlySchedule]) -> list[RotaEntryDTO]:
    return [
        RotaEntryDTO(
            date=row.date,
            member_id=row.member_id,
            service_id=row.schedule_type_id,
            service_name=row.schedule_type.name,
            start_time=row.schedule_type.start_time,
            month_first_saved_at=getattr(row, "month_first_saved_at"),
            member_gender=row.member.gender or None,
        )
        for row in rows
    ]
