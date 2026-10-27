"""``send_schedule_reminders`` end to end (specs/024-schedule-reminders FR-016, FR-017)."""

import json
from collections.abc import Iterator
from datetime import date, datetime, time
from io import StringIO
from zoneinfo import ZoneInfo

import pytest
from dependency_injector import providers
from django.core.management import call_command

from config.di import Container
from conftest import make_user
from core.models import ChurchService, DeviceToken
from core.tests.fakes import FakePushSender
from features.members.models.member import Member
from features.schedule.management.commands.send_schedule_reminders import summary_line
from features.schedule.models import MonthlySchedule
from features.schedule.reminder_dtos import KindRunReport, ReminderKind
from features.schedule.tests.fakes import FixedClock

SP = ZoneInfo("America/Sao_Paulo")


@pytest.fixture
def sender(di_container: Container) -> Iterator[FakePushSender]:
    fake = FakePushSender()
    with di_container.push_sender.override(providers.Object(fake)):
        yield fake


def _run_at(container: Container, moment: datetime, *args: str) -> str:
    out = StringIO()
    with container.clock.override(providers.Object(FixedClock(moment))):
        call_command("send_schedule_reminders", *args, stdout=out)
    return out.getvalue().strip()


def _rota_with_linked_member() -> ChurchService:
    user = make_user(username="ana")
    member = Member.objects.create(name="Ana")
    user.profile.member = member
    user.profile.member_access = True
    user.profile.save()
    DeviceToken.objects.create(user=user, token="ana-phone")
    thursday = ChurchService.objects.create(
        name="Quinta de Oração", weekday=5, start_time=time(19, 30), end_time=time(21, 0)
    )
    MonthlySchedule.objects.create(
        date=date(2026, 10, 29),
        schedule_type=thursday,
        member=member,
        created_at=datetime(2026, 10, 1, 9, 0, tzinfo=SP),
    )
    return thursday


@pytest.mark.django_db
class TestCommand:
    def test_nothing_due_is_silent(self, di_container: Container, sender: FakePushSender) -> None:
        assert _run_at(di_container, datetime(2026, 10, 27, 10, 0, tzinfo=SP)) == ""

    def test_eve_sends_once(self, di_container: Container, sender: FakePushSender) -> None:
        thursday = _rota_with_linked_member()
        evening = datetime(2026, 10, 28, 19, 3, tzinfo=SP)
        assert _run_at(di_container, evening) == (
            f"kind=schedule_eve occasions=2026-10-29/{thursday.pk} claimed=1 devices=1 sent=1"
        )
        assert _run_at(di_container, evening) == ""
        assert _run_at(di_container, evening, "-v", "2").startswith("kind=schedule_eve")
        [(tokens, message)] = sender.calls
        assert tokens == ["ana-phone"]
        assert json.loads(message.as_data()["slots"]) == [
            {"date": "2026-10-29", "service": "Quinta de Oração", "time": "19:30"}
        ]


def test_summary_line_without_occasions() -> None:
    assert summary_line(KindRunReport(kind=ReminderKind.WEEK)) == (
        "kind=schedule_week occasions=- claimed=0 devices=0 sent=0"
    )
