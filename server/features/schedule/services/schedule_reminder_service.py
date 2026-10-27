import logging
from collections.abc import Callable
from datetime import datetime
from uuid import UUID, uuid4

from django.utils import timezone

from core.application.dtos.push_dtos import PushMessage
from core.application.push_service import PushService
from core.domain.push import PushMessageType
from core.repositories.interfaces import MemberAccountRepository
from core.time.clock import Clock
from features.schedule.reminder_dtos import (
    KindRunReport,
    ReminderClaimKey,
    ReminderKind,
    RotaEntryDTO,
    ScheduleReminderRunReport,
)
from features.schedule.repositories.interfaces import RotaReminderRepository
from features.schedule.services.reminder_rules import (
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

logger = logging.getLogger(__name__)

ClaimGroups = dict[ReminderClaimKey, list[RotaEntryDTO]]


class ScheduleReminderService:
    """Tells each rota member by push that they serve: the month's publication, the Monday week
    summary and the eve of each entry (specs/024-schedule-reminders). Run every minute by
    ``send_schedule_reminders``.

    Each (kind, member, occasion) is claimed in the database *before* its push goes out, so a
    restart or an overlapping run can at worst lose a reminder, never send one twice, and a
    failing provider is not retried every minute (spec FR-013, FR-015).
    """

    def __init__(
        self,
        reminder_repository: RotaReminderRepository,
        member_account_repository: MemberAccountRepository,
        push_service: PushService,
        clock: Clock,
    ) -> None:
        self._reminders = reminder_repository
        self._accounts = member_account_repository
        self._push = push_service
        self._clock = clock

    def run(self) -> ScheduleReminderRunReport:
        """One report per kind whose window is open now; publication first, so on a Monday the
        broad message arrives before the week summary.

        >>> ScheduleReminderService(...).run().kinds[0].kind
        <ReminderKind.EVE: 'schedule_eve'>
        """
        now = timezone.localtime(self._clock.now())
        run_id = uuid4()
        reports = [
            report
            for report in (
                self._publications(now, run_id),
                self._week(now, run_id),
                self._eve(now, run_id),
            )
            if report is not None
        ]
        for report in reports:
            _log(report)
        return ScheduleReminderRunReport(kinds=reports)

    def _publications(self, now: datetime, run_id: UUID) -> KindRunReport | None:
        months = self._reminders.months_first_saved_between(*publishing_first_saves(now))
        if not months:
            return None
        entries = self._reminders.entries_of_months_from(months, now.date())
        return self._send(ReminderKind.PUBLISHED, entries, _month_of, now, run_id)

    def _week(self, now: datetime, run_id: UUID) -> KindRunReport | None:
        week = week_range(now)
        if week is None:
            return None
        occasion = week_occasion(week[0])
        entries = self._reminders.entries_between(*week)
        return self._send(ReminderKind.WEEK, entries, lambda _: occasion, now, run_id)

    def _eve(self, now: datetime, run_id: UUID) -> KindRunReport | None:
        day = eve_date(now)
        if day is None:
            return None
        entries = self._reminders.entries_between(day, day)
        return self._send(ReminderKind.EVE, entries, eve_occasion, now, run_id)

    def _send(
        self,
        kind: ReminderKind,
        entries: list[RotaEntryDTO],
        occasion_of: Callable[[RotaEntryDTO], str],
        now: datetime,
        run_id: UUID,
    ) -> KindRunReport:
        # Only months that can no longer change: nobody is told they serve and then removed (FR-019).
        final = [e for e in entries if is_past_overwrite_window(e.month_first_saved_at, now)]
        groups = group_by_claim(final, occasion_of)
        users = self._accounts.user_ids_by_member({key.member_id for key in groups})
        # A member without an account is not claimed, so a link made later today still counts (R-09).
        won = self._reminders.claim(kind, [key for key in groups if key.member_id in users], run_id)
        report = KindRunReport(
            kind=kind, occasions=sorted({key.occasion for key in groups}), claimed=len(won)
        )
        return self._notify(report, groups, users, won)

    def _notify(
        self,
        report: KindRunReport,
        groups: ClaimGroups,
        users: dict[int, UUID],
        won: set[ReminderClaimKey],
    ) -> KindRunReport:
        devices = sent = 0
        for key in sorted(won, key=lambda k: (k.occasion, k.member_id)):
            message = _message(report.kind, key, groups[key])
            outcome = self._push.notify({users[key.member_id]}, message)
            devices, sent = devices + outcome.devices, sent + outcome.sent
        return report.model_copy(update={"devices": devices, "sent": sent})


def _month_of(entry: RotaEntryDTO) -> str:
    return month_occasion(entry.date.year, entry.date.month)


def _message(kind: ReminderKind, key: ReminderClaimKey, entries: list[RotaEntryDTO]) -> PushMessage:
    month = key.occasion if kind is ReminderKind.PUBLISHED else None
    # Every entry of a group is the same member, so any one carries their gender.
    return PushMessage(
        type=PushMessageType(kind.value),
        slots=slots_json(entries),
        month=month,
        gender=entries[0].member_gender,
    )


def _log(report: KindRunReport) -> None:
    # An open window with nothing to send happens every minute from 19:00; keep that out of INFO.
    level = logging.INFO if report.claimed else logging.DEBUG
    logger.log(
        level,
        "schedule_reminder_run",
        extra={
            "reminder_kind": report.kind.value,
            "occasions": report.occasions,
            "claimed": report.claimed,
            "devices": report.devices,
            "sent": report.sent,
        },
    )
