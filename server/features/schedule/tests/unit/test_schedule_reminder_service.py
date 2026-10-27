"""Rota reminders (specs/024-schedule-reminders US1–US3)."""

import json
from datetime import date, datetime, time
from uuid import uuid4
from zoneinfo import ZoneInfo

from core.application.dtos.push_dtos import PushMessage
from core.application.push_service import PushService
from core.domain.push import PushMessageType
from core.tests.fakes import FakeDeviceTokenRepository, FakeMemberAccountRepository, FakePushSender
from features.schedule.reminder_dtos import ReminderKind, RotaEntryDTO, ScheduleReminderRunReport
from features.schedule.services.schedule_reminder_service import ScheduleReminderService
from features.schedule.tests.fakes import FakeRotaReminderRepository, FixedClock

SP = ZoneInfo("America/Sao_Paulo")
ANA_MEMBER, BIA_MEMBER, NO_ACCOUNT_MEMBER = 7, 9, 11
ANA, BIA = uuid4(), uuid4()
OCTOBER_SAVED = datetime(2026, 10, 1, 9, 0, tzinfo=SP)
THURSDAY = date(2026, 10, 29)
MONDAY = date(2026, 10, 26)


def _at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=SP)


def _entry(
    day: date,
    member_id: int = ANA_MEMBER,
    service: tuple[int, str] = (5, "Quinta de Oração"),
    saved: datetime = OCTOBER_SAVED,
    gender: str | None = None,
) -> RotaEntryDTO:
    return RotaEntryDTO(
        date=day,
        member_id=member_id,
        service_id=service[0],
        service_name=service[1],
        start_time=time(19, 30),
        month_first_saved_at=saved,
        member_gender=gender,
    )


class _World:
    def __init__(self, entries: list[RotaEntryDTO], sender: FakePushSender | None = None) -> None:
        self.reminders = FakeRotaReminderRepository(entries)
        self.accounts = FakeMemberAccountRepository({ANA_MEMBER: ANA, BIA_MEMBER: BIA})
        self.tokens = FakeDeviceTokenRepository({"ana-phone": ANA, "bia-phone": BIA})
        self.sender = sender or FakePushSender()

    def run_at(self, moment: datetime) -> ScheduleReminderRunReport:
        """A fresh service per run, as each loop iteration is a new process."""
        service = ScheduleReminderService(
            self.reminders, self.accounts, PushService(self.tokens, self.sender), FixedClock(moment)
        )
        return service.run()

    def sent(self, kind: PushMessageType) -> list[tuple[list[str], PushMessage]]:
        return [(tokens, message) for tokens, message in self.sender.calls if message.type is kind]


def _kinds(report: ScheduleReminderRunReport) -> dict[ReminderKind, int]:
    return {kind_report.kind: kind_report.claimed for kind_report in report.kinds}


def _slots(message: PushMessage) -> list[dict[str, str]]:
    assert message.slots is not None
    slots: list[dict[str, str]] = json.loads(message.slots)
    return slots


class TestEveReminder:
    def test_sent_once_from_seven_pm(self) -> None:
        world = _World([_entry(THURSDAY)])
        assert ReminderKind.EVE not in _kinds(world.run_at(_at(date(2026, 10, 28), 18, 59)))
        assert _kinds(world.run_at(_at(date(2026, 10, 28), 19, 5)))[ReminderKind.EVE] == 1
        assert _kinds(world.run_at(_at(date(2026, 10, 28), 19, 30)))[ReminderKind.EVE] == 0
        [(tokens, message)] = world.sent(PushMessageType.SCHEDULE_EVE)
        assert tokens == ["ana-phone"]
        assert _slots(message) == [
            {"date": "2026-10-29", "service": "Quinta de Oração", "time": "19:30"}
        ]
        assert message.month is None

    def test_not_sent_once_the_day_started(self) -> None:
        world = _World([_entry(THURSDAY)])
        world.run_at(_at(THURSDAY, 0, 10))
        assert world.sender.calls == []

    def test_one_message_per_entry(self) -> None:
        sunday = date(2026, 11, 1)
        morning = _entry(sunday, service=(2, "Escola Dominical"))
        evening = _entry(sunday, service=(1, "Domingo Liturgia de Adoração"))
        world = _World([morning, evening])
        world.run_at(_at(date(2026, 10, 31), 19, 0))
        assert len(world.sent(PushMessageType.SCHEDULE_EVE)) == 2

    def test_member_without_account_gets_nothing_and_is_not_claimed(self) -> None:
        world = _World([_entry(THURSDAY, member_id=NO_ACCOUNT_MEMBER)])
        world.run_at(_at(date(2026, 10, 28), 19, 5))
        assert world.sender.calls == [] and world.reminders.claims == set()
        world.accounts.accounts[NO_ACCOUNT_MEMBER] = BIA
        world.run_at(_at(date(2026, 10, 28), 21, 0))
        assert len(world.sent(PushMessageType.SCHEDULE_EVE)) == 1

    def test_provider_failure_still_claims(self) -> None:
        world = _World([_entry(THURSDAY)], sender=FakePushSender(raises=ConnectionError("down")))
        world.run_at(_at(date(2026, 10, 28), 19, 1))
        world.run_at(_at(date(2026, 10, 28), 19, 2))
        assert len(world.sender.calls) == 1

    def test_month_inside_overwrite_window_is_not_used(self) -> None:
        saved = _at(date(2026, 10, 28), 19, 0)
        world = _World([_entry(THURSDAY, saved=saved)])
        world.run_at(_at(date(2026, 10, 28), 19, 5))
        assert world.sent(PushMessageType.SCHEDULE_EVE) == []
        world.run_at(_at(date(2026, 10, 28), 19, 31))
        assert len(world.sent(PushMessageType.SCHEDULE_EVE)) == 1

    def test_no_device_still_claims(self) -> None:
        world = _World([_entry(THURSDAY)])
        world.tokens.owners.clear()
        report = world.run_at(_at(date(2026, 10, 28), 19, 5))
        assert _kinds(report)[ReminderKind.EVE] == 1 and world.sender.calls == []


class TestWeekSummary:
    def test_one_message_with_the_week_in_order(self) -> None:
        tuesday = _entry(date(2026, 10, 27), service=(3, "Terça de Oração"))
        sunday = _entry(date(2026, 11, 1), service=(1, "Domingo Liturgia de Adoração"))
        world = _World([sunday, tuesday])
        world.run_at(_at(MONDAY, 8, 3))
        [(tokens, message)] = world.sent(PushMessageType.SCHEDULE_WEEK)
        assert tokens == ["ana-phone"]
        assert [slot["date"] for slot in _slots(message)] == ["2026-10-27", "2026-11-01"]

    def test_member_without_entries_this_week_gets_nothing(self) -> None:
        world = _World(
            [_entry(date(2026, 10, 27)), _entry(date(2026, 11, 3), member_id=BIA_MEMBER)]
        )
        world.run_at(_at(MONDAY, 8, 3))
        assert [tokens for tokens, _ in world.sent(PushMessageType.SCHEDULE_WEEK)] == [
            ["ana-phone"]
        ]

    def test_once_per_monday(self) -> None:
        world = _World([_entry(date(2026, 10, 27))])
        world.run_at(_at(MONDAY, 8, 3))
        world.run_at(_at(MONDAY, 9, 0))
        assert len(world.sent(PushMessageType.SCHEDULE_WEEK)) == 1

    def test_late_run_same_day_sends_next_day_does_not(self) -> None:
        late = _World([_entry(date(2026, 10, 28))])
        late.run_at(_at(MONDAY, 15, 0))
        assert len(late.sent(PushMessageType.SCHEDULE_WEEK)) == 1
        missed = _World([_entry(date(2026, 10, 28))])
        missed.run_at(_at(date(2026, 10, 27), 8, 30))
        assert missed.sent(PushMessageType.SCHEDULE_WEEK) == []

    def test_before_eight_sends_nothing(self) -> None:
        world = _World([_entry(date(2026, 10, 27))])
        world.run_at(_at(MONDAY, 7, 59))
        assert world.sender.calls == []

    def test_tuesday_entry_gets_summary_and_eve_on_monday(self) -> None:
        world = _World([_entry(date(2026, 10, 27), service=(3, "Terça de Oração"))])
        world.run_at(_at(MONDAY, 8, 0))
        world.run_at(_at(MONDAY, 19, 0))
        assert len(world.sent(PushMessageType.SCHEDULE_WEEK)) == 1
        assert len(world.sent(PushMessageType.SCHEDULE_EVE)) == 1


class TestPublication:
    NOVEMBER_SAVED = datetime(2026, 10, 30, 10, 0, tzinfo=SP)

    def _november(self) -> _World:
        return _World(
            [
                _entry(date(2026, 11, 5), saved=self.NOVEMBER_SAVED),
                _entry(
                    date(2026, 11, 3), saved=self.NOVEMBER_SAVED, service=(3, "Terça de Oração")
                ),
                _entry(date(2026, 11, 12), member_id=BIA_MEMBER, saved=self.NOVEMBER_SAVED),
            ]
        )

    def test_sent_once_after_the_window_closes(self) -> None:
        world = self._november()
        world.run_at(_at(date(2026, 10, 30), 10, 20))
        assert world.sender.calls == []
        world.run_at(_at(date(2026, 10, 30), 10, 31))
        world.run_at(_at(date(2026, 10, 30), 10, 45))
        sent = world.sent(PushMessageType.SCHEDULE_PUBLISHED)
        assert sorted(tokens[0] for tokens, _ in sent) == ["ana-phone", "bia-phone"]
        ana_message = next(message for tokens, message in sent if tokens == ["ana-phone"])
        assert ana_message.month == "2026-11"
        assert [slot["date"] for slot in _slots(ana_message)] == ["2026-11-03", "2026-11-05"]

    def test_next_day_is_too_late(self) -> None:
        world = self._november()
        world.run_at(_at(date(2026, 10, 31), 10, 31))
        assert world.sent(PushMessageType.SCHEDULE_PUBLISHED) == []

    def test_only_entries_from_today(self) -> None:
        saved = datetime(2026, 10, 10, 10, 0, tzinfo=SP)
        world = _World(
            [
                _entry(date(2026, 10, 5), saved=saved),
                _entry(date(2026, 10, 20), member_id=BIA_MEMBER, saved=saved),
            ]
        )
        world.run_at(_at(date(2026, 10, 10), 10, 31))
        [(tokens, message)] = world.sent(PushMessageType.SCHEDULE_PUBLISHED)
        assert tokens == ["bia-phone"] and message.month == "2026-10"

    def test_messages_never_carry_another_member_or_a_name(self) -> None:
        world = self._november()
        world.run_at(_at(date(2026, 10, 30), 10, 31))
        for tokens, message in world.sent(PushMessageType.SCHEDULE_PUBLISHED):
            dates = {slot["date"] for slot in _slots(message)}
            expected = {"2026-11-12"} if tokens == ["bia-phone"] else {"2026-11-03", "2026-11-05"}
            assert dates == expected
            assert set(message.as_data()) == {"type", "month", "slots"}


class TestRecipientGender:
    def test_carries_the_members_own_gender(self) -> None:
        world = _World([_entry(THURSDAY, gender="F"), _entry(THURSDAY, BIA_MEMBER, gender="M")])
        world.run_at(_at(date(2026, 10, 28), 19, 5))
        sent = world.sent(PushMessageType.SCHEDULE_EVE)
        by_token = {tokens[0]: message.gender for tokens, message in sent}
        assert by_token == {"ana-phone": "F", "bia-phone": "M"}

    def test_no_gender_recorded_leaves_the_key_out(self) -> None:
        world = _World([_entry(THURSDAY)])
        world.run_at(_at(date(2026, 10, 28), 19, 5))
        [(_, message)] = world.sent(PushMessageType.SCHEDULE_EVE)
        assert "gender" not in message.as_data()
