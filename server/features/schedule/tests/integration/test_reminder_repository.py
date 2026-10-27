"""Rota reminder reads and claims (specs/024-schedule-reminders R-01, R-02, R-04)."""

from datetime import date, datetime, time
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from core.models import ChurchService
from features.members.models.member import Member
from features.schedule.models import MonthlySchedule, ScheduleReminderClaim
from features.schedule.reminder_dtos import ReminderClaimKey, ReminderKind
from features.schedule.repositories.reminder_repository import RotaReminderRepositoryImpl

SP = ZoneInfo("America/Sao_Paulo")


def _service(name: str, weekday: int, start: time) -> ChurchService:
    return ChurchService.objects.create(
        name=name, weekday=weekday, start_time=start, end_time=time(start.hour + 1, start.minute)
    )


def _row(day: date, service: ChurchService, member: Member, saved: datetime) -> MonthlySchedule:
    return MonthlySchedule.objects.create(
        date=day, schedule_type=service, member=member, created_at=saved
    )


@pytest.mark.django_db
class TestRotaReminderRepository:
    repository = RotaReminderRepositoryImpl()

    @pytest.fixture(autouse=True)
    def _rota(self) -> None:
        self.ana = Member.objects.create(name="Ana")
        self.thursday = _service("Quinta de Oração", 5, time(19, 30))
        self.sunday_school = _service("Escola Dominical", 1, time(9, 0))
        self.first_save = datetime(2026, 10, 1, 9, 0, tzinfo=SP)
        _row(date(2026, 10, 29), self.thursday, self.ana, self.first_save)
        _row(
            date(2026, 10, 4), self.sunday_school, self.ana, datetime(2026, 10, 1, 9, 20, tzinfo=SP)
        )
        self.november_save = datetime(2026, 10, 30, 10, 0, tzinfo=SP)
        _row(date(2026, 11, 5), self.thursday, self.ana, self.november_save)

    def test_entries_between_carry_service_and_month_first_save(self) -> None:
        [entry] = self.repository.entries_between(date(2026, 10, 29), date(2026, 10, 29))
        assert (entry.member_id, entry.service_id) == (self.ana.pk, self.thursday.pk)
        assert entry.service_name == "Quinta de Oração" and entry.start_time == time(19, 30)
        assert entry.month_first_saved_at == self.first_save
        assert entry.member_gender is None

    def test_entries_carry_the_members_gender(self) -> None:
        Member.objects.filter(pk=self.ana.pk).update(gender="F")
        [entry] = self.repository.entries_between(date(2026, 10, 29), date(2026, 10, 29))
        assert entry.member_gender == "F"

    def test_entries_between_cross_months_ordered(self) -> None:
        entries = self.repository.entries_between(date(2026, 10, 1), date(2026, 11, 30))
        assert [e.date for e in entries] == [
            date(2026, 10, 4),
            date(2026, 10, 29),
            date(2026, 11, 5),
        ]
        assert entries[-1].month_first_saved_at == self.november_save

    def test_entries_of_months_from(self) -> None:
        entries = self.repository.entries_of_months_from({(2026, 10)}, date(2026, 10, 10))
        assert [e.date for e in entries] == [date(2026, 10, 29)]
        assert self.repository.entries_of_months_from(set(), date(2026, 10, 1)) == []

    def test_months_by_first_save(self) -> None:
        since, until = (
            datetime(2026, 10, 30, 0, 0, tzinfo=SP),
            datetime(2026, 10, 30, 11, 0, tzinfo=SP),
        )
        assert self.repository.months_first_saved_between(since, until) == [(2026, 11)]
        # October's first save is 09:00 on the 1st; its later row at 09:20 does not count.
        on_first = (
            datetime(2026, 10, 1, 9, 10, tzinfo=SP),
            datetime(2026, 10, 1, 23, 0, tzinfo=SP),
        )
        assert self.repository.months_first_saved_between(*on_first) == []

    def test_claim_once(self) -> None:
        key = ReminderClaimKey(member_id=self.ana.pk, occasion="2026-10-29/5")
        assert self.repository.claim(ReminderKind.EVE, [key], uuid4()) == {key}
        assert self.repository.claim(ReminderKind.EVE, [key], uuid4()) == set()
        assert self.repository.claim(ReminderKind.WEEK, [key], uuid4()) == {key}

    def test_overlapping_runs_split_the_claims(self) -> None:
        first = ReminderClaimKey(member_id=self.ana.pk, occasion="2026-11")
        bia = Member.objects.create(name="Bia")
        second = ReminderClaimKey(member_id=bia.pk, occasion="2026-11")
        assert self.repository.claim(ReminderKind.PUBLISHED, [first], uuid4()) == {first}
        assert self.repository.claim(ReminderKind.PUBLISHED, [first, second], uuid4()) == {second}
        assert ScheduleReminderClaim.objects.count() == 2

    def test_claim_nothing(self) -> None:
        assert self.repository.claim(ReminderKind.EVE, [], uuid4()) == set()

    def test_claim_str_has_ids_only(self) -> None:
        key = ReminderClaimKey(member_id=self.ana.pk, occasion="2026-11")
        self.repository.claim(ReminderKind.PUBLISHED, [key], uuid4())
        assert str(ScheduleReminderClaim.objects.get()) == (
            f"schedule_published 2026-11 member={self.ana.pk}"
        )
