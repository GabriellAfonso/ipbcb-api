import logging
from datetime import date

from django.utils import timezone

from core.application.dtos.push_dtos import PushMessage
from core.application.push_service import PushService
from core.application.worship_access_service import WorshipAccessService
from core.domain.push import PushMessageType
from core.time.clock import Clock
from features.songs.repositories.interfaces import SetlistRepository
from features.songs.services.setlist_rules import current_reminder_slot
from features.songs.setlist_dtos import ReminderRunReport

logger = logging.getLogger(__name__)


class SetlistReminderService:
    """Sunday-night nudge to register the played songs (specs/017-sunday-setlist-push US5,
    research R-10). Run every minute by ``send_setlist_reminders``.

    The window is claimed on the setlist row *before* the push goes out: a crash, a restart or
    an overlapping run can at worst lose one reminder, never send one twice, and a failing
    provider is not retried every minute inside the same window (FR-018, FR-020).
    """

    def __init__(
        self,
        setlist_repository: SetlistRepository,
        worship_access_service: WorshipAccessService,
        push_service: PushService,
        clock: Clock,
    ) -> None:
        self._setlists = setlist_repository
        self._worship = worship_access_service
        self._push = push_service
        self._clock = clock

    def run(self) -> ReminderRunReport:
        """>>> SetlistReminderService(...).run().outcome
        'outside_window'
        """
        now_local = timezone.localtime(self._clock.now())
        slot = current_reminder_slot(now_local)
        if slot is None:
            return _done(ReminderRunReport(outcome="outside_window"))
        day = now_local.date()
        report = self._skip_reason(day)
        if report is not None:
            return _done(report.model_copy(update={"slot": slot}))
        if not self._setlists.claim_reminder_slot(day, slot):
            return _done(ReminderRunReport(outcome="already_sent", setlist_date=day, slot=slot))
        message = PushMessage(type=PushMessageType.CONFIRM_PLAYS, date=day)
        push = self._push.notify(self._worship.reminder_recipients(), message)
        return _done(ReminderRunReport(outcome="sent", setlist_date=day, slot=slot, push=push))

    def _skip_reason(self, day: date) -> ReminderRunReport | None:
        if self._setlists.get_by_date(day) is None:
            return ReminderRunReport(outcome="no_setlist")
        if self._setlists.has_plays(day):
            return ReminderRunReport(outcome="confirmed", setlist_date=day)
        return None


def _done(report: ReminderRunReport) -> ReminderRunReport:
    # The loop runs every minute: outside Sunday night that is 1,400 lines a day saying nothing.
    level = logging.DEBUG if report.outcome == "outside_window" else logging.INFO
    logger.log(
        level,
        "setlist_reminder_run",
        extra={
            "outcome": report.outcome,
            "setlist_date": report.setlist_date.isoformat() if report.setlist_date else None,
            "slot": report.slot.isoformat() if report.slot else None,
        },
    )
    return report
