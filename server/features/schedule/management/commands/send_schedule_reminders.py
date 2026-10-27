"""Send the rota reminders that are due: publication, Monday week summary, eve of each entry.

Run every 60 s by the ``ipbcb_setlist_reminder`` loop in compose.prod.yml. Safe to run any number
of times: each (kind, member, occasion) is claimed before sending, so it goes out at most once
(specs/024-schedule-reminders FR-013, research R-02, R-08).
"""

from typing import Any

from dependency_injector.wiring import Provide, inject
from django.core.management.base import BaseCommand

from config.di import Container
from features.schedule.reminder_dtos import KindRunReport, ScheduleReminderRunReport
from features.schedule.services.schedule_reminder_service import ScheduleReminderService


@inject
def _run(
    reminder_service: ScheduleReminderService = Provide[Container.schedule_reminder_service],
) -> ScheduleReminderRunReport:
    return reminder_service.run()


def summary_line(report: KindRunReport) -> str:
    """>>> summary_line(KindRunReport(kind=ReminderKind.EVE, occasions=["2026-10-29/3"]))
    'kind=schedule_eve occasions=2026-10-29/3 claimed=0 devices=0 sent=0'
    """
    occasions = ",".join(report.occasions) or "-"
    return (
        f"kind={report.kind.value} occasions={occasions} claimed={report.claimed} "
        f"devices={report.devices} sent={report.sent}"
    )


class Command(BaseCommand):
    help = "Send the rota reminders (publication, week summary, eve) that are due now."

    def handle(self, *args: Any, **options: Any) -> None:
        # Always exit 0: the loop runs again in a minute, and a failing exit would only make the
        # container restart policy fight the loop.
        report = _run()
        # Silent when nothing was claimed unless -v 2: the eve window alone is open five hours a
        # day, and the loop would otherwise log a line a minute.
        for kind_report in report.kinds:
            if kind_report.claimed or options["verbosity"] >= 2:
                self.stdout.write(summary_line(kind_report))
