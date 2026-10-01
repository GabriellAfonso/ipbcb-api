"""Send the Sunday-night "confirm the played songs" reminder when one is due.

Run every 60 s by the ``ipbcb_setlist_reminder`` loop in compose.prod.yml. Safe to run any
number of times: each half-hour window is claimed on the setlist before sending, so it goes out
at most once (specs/017-sunday-setlist-push US5, research R-10, R-11).
"""

from typing import Any

from dependency_injector.wiring import Provide, inject
from django.core.management.base import BaseCommand

from config.di import Container
from features.songs.services.setlist_reminder_service import SetlistReminderService
from features.songs.setlist_dtos import ReminderRunReport


@inject
def _run(
    reminder_service: SetlistReminderService = Provide[Container.setlist_reminder_service],
) -> ReminderRunReport:
    return reminder_service.run()


def summary_line(report: ReminderRunReport) -> str:
    """>>> summary_line(ReminderRunReport(outcome="outside_window"))
    'outcome=outside_window date=- slot=- devices=0 sent=0'
    """
    day = report.setlist_date.isoformat() if report.setlist_date else "-"
    slot = report.slot.strftime("%H:%M") if report.slot else "-"
    devices = report.push.devices if report.push else 0
    sent = report.push.sent if report.push else 0
    return f"outcome={report.outcome} date={day} slot={slot} devices={devices} sent={sent}"


class Command(BaseCommand):
    help = "Send the Sunday-night reminder to register the played songs, when one is due."

    def handle(self, *args: Any, **options: Any) -> None:
        # Always exit 0: the loop runs again in a minute, and a failing exit would only make the
        # container restart policy fight the loop.
        report = _run()
        # Silent outside the window unless -v 2: the loop would otherwise log a line a minute.
        if report.outcome != "outside_window" or options["verbosity"] >= 2:
            self.stdout.write(summary_line(report))
