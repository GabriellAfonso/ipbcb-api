"""Sunday-night reminder (specs/017-sunday-setlist-push US5, research R-10)."""

from datetime import date, datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from core.application.access_service import AccessService
from core.application.push_service import PushService
from core.application.worship_access_service import WorshipAccessService
from core.domain.push import PushMessageType
from core.tests.fakes import (
    FakeDeviceTokenRepository,
    FakePushSender,
    FakeRoleGrantRepository,
    FakeWorshipMembership,
)
from features.songs.services.setlist_reminder_service import SetlistReminderService
from features.songs.setlist_dtos import SetlistItemInput
from features.songs.tests.fakes import FakeSetlistRepository, FrozenClock

SP = ZoneInfo("America/Sao_Paulo")
SUNDAY = date(2026, 10, 4)
# LEADER: manages songs and plays in the band. BAND: band only. ADMIN: manages, not in the band.
LEADER, BAND, ADMIN = uuid4(), uuid4(), uuid4()


class _World:
    def __init__(self, sender: FakePushSender | None = None, with_setlist: bool = True) -> None:
        self.setlists = FakeSetlistRepository()
        if with_setlist:
            item = SetlistItemInput(song_id=1, position=1, tone="G")
            self.setlists.replace(SUNDAY, LEADER, [item], datetime(2026, 10, 1, tzinfo=SP))
        self.sender = sender or FakePushSender()
        self.tokens = FakeDeviceTokenRepository(
            {"leader-phone": LEADER, "band-phone": BAND, "admin-phone": ADMIN}
        )
        roles = FakeRoleGrantRepository([], [], level_holders={LEADER, ADMIN})
        self.worship = WorshipAccessService(
            FakeWorshipMembership({LEADER, BAND}), AccessService(roles)
        )

    def run_at(self, hour: int, minute: int, day: date = SUNDAY) -> str:
        """A fresh service per run, as each loop iteration is a new process; state lives only
        in the repository, like the setlist row in production."""
        moment = datetime(day.year, day.month, day.day, hour, minute, tzinfo=SP)
        service = SetlistReminderService(
            self.setlists, self.worship, PushService(self.tokens, self.sender), FrozenClock(moment)
        )
        return service.run().outcome


def test_spec_scenario_sends_once_per_window_until_confirmed() -> None:
    world = _World()
    outcomes = [world.run_at(h, m) for h, m in ((20, 59), (21, 5), (21, 10), (21, 35), (22, 1))]
    assert outcomes == ["outside_window", "sent", "already_sent", "sent", "sent"]
    world.setlists.played_dates.add(SUNDAY)
    assert world.run_at(22, 31) == "confirmed"
    assert len(world.sender.calls) == 3


def test_recipients_are_managers_in_the_band() -> None:
    world = _World()
    world.run_at(21, 0)
    [(tokens, message)] = world.sender.calls
    assert tokens == ["leader-phone"]
    assert message.type is PushMessageType.CONFIRM_PLAYS and message.date == SUNDAY


def test_no_setlist_today_sends_nothing() -> None:
    world = _World(with_setlist=False)
    assert world.run_at(21, 5) == "no_setlist"
    assert world.sender.calls == []


def test_saturday_night_is_outside_the_window() -> None:
    assert _World().run_at(22, 0, day=date(2026, 10, 3)) == "outside_window"


def test_missed_windows_are_not_sent_late() -> None:
    world = _World()
    assert world.run_at(22, 40) == "sent"
    assert world.setlists.slots[SUNDAY] == datetime(2026, 10, 4, 22, 30, tzinfo=SP)
    assert len(world.sender.calls) == 1


def test_provider_failure_still_consumes_the_window() -> None:
    world = _World(sender=FakePushSender(raises=ConnectionError("down")))
    assert world.run_at(21, 1) == "sent"
    assert world.run_at(21, 2) == "already_sent"
    assert len(world.sender.calls) == 1


def test_last_window_runs_until_midnight() -> None:
    world = _World()
    assert world.run_at(23, 59) == "sent"
    assert world.setlists.slots[SUNDAY].hour == 23 and world.setlists.slots[SUNDAY].minute == 30
