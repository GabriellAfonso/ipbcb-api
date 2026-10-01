from collections.abc import Iterator
from datetime import datetime
from io import StringIO
from zoneinfo import ZoneInfo

import pytest
from dependency_injector import providers
from django.core.management import call_command

from config.di import Container
from conftest import link_to_ministry, make_role_client
from core.domain.access import Role
from core.models import DeviceToken
from core.tests.fakes import FakePushSender
from features.songs.management.commands.send_setlist_reminders import summary_line
from features.songs.models import Setlist
from features.songs.setlist_dtos import ReminderRunReport
from features.songs.tests.fakes import FrozenClock

SP = ZoneInfo("America/Sao_Paulo")


@pytest.fixture
def sender(di_container: Container) -> Iterator[FakePushSender]:
    fake = FakePushSender()
    with di_container.push_sender.override(providers.Object(fake)):
        yield fake


def _run_at(container: Container, moment: datetime, *args: str) -> str:
    out = StringIO()
    with container.clock.override(providers.Object(FrozenClock(moment))):
        call_command("send_setlist_reminders", *args, stdout=out)
    return out.getvalue().strip()


@pytest.mark.django_db
class TestCommand:
    def test_outside_window_is_silent_by_default(self, di_container: Container) -> None:
        weekday = datetime(2026, 10, 1, 21, 0, tzinfo=SP)
        assert _run_at(di_container, weekday) == ""
        assert _run_at(di_container, weekday, "-v", "2").startswith("outcome=outside_window")

    def test_sunday_night_sends_once(self, di_container: Container, sender: FakePushSender) -> None:
        _, leader = make_role_client(Role.LEADER, username="leader")
        link_to_ministry(leader)
        DeviceToken.objects.create(user=leader, token="leader-phone")
        Setlist.objects.create(date="2026-10-04", saved_at=datetime(2026, 10, 1, tzinfo=SP))
        night = datetime(2026, 10, 4, 21, 3, tzinfo=SP)
        assert _run_at(di_container, night) == (
            "outcome=sent date=2026-10-04 slot=21:00 devices=1 sent=1"
        )
        assert _run_at(di_container, night).startswith("outcome=already_sent")
        assert len(sender.calls) == 1


def test_summary_line_without_push() -> None:
    assert summary_line(ReminderRunReport(outcome="no_setlist")) == (
        "outcome=no_setlist date=- slot=- devices=0 sent=0"
    )
