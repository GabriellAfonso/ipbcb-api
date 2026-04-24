import pytest
from datetime import date, time

from features.members.models.member import Member
from features.schedule.models.schedule import (
    MemberScheduleConfig,
    MonthlySchedule,
    ScheduleType,
)


@pytest.mark.django_db
class TestScheduleTypeStr:
    def test_returns_name_and_id(self) -> None:
        st = ScheduleType.objects.create(name="Culto", weekday=1, time=time(9, 0))
        assert str(st) == f"Culto - {st.id}"


@pytest.mark.django_db
class TestMemberScheduleConfigStr:
    def test_returns_member_and_schedule_type(self) -> None:
        m = Member.objects.create(name="Alice")
        st = ScheduleType.objects.create(name="Culto", weekday=1, time=time(9, 0))
        cfg = MemberScheduleConfig.objects.create(member=m, schedule_type=st)
        assert str(cfg) == "Alice - Culto"


@pytest.mark.django_db
class TestMonthlyScheduleStr:
    def test_returns_member_date_and_type(self) -> None:
        m = Member.objects.create(name="Bob")
        st = ScheduleType.objects.create(name="Culto", weekday=1, time=time(9, 0))
        ms = MonthlySchedule.objects.create(date=date(2026, 5, 3), schedule_type=st, member=m)
        assert str(ms) == "Bob - 03/05/2026 - Culto"


@pytest.mark.django_db
class TestMonthlyScheduleSave:
    def test_save_sets_year_and_month_from_date(self) -> None:
        m = Member.objects.create(name="Carol")
        st = ScheduleType.objects.create(name="Culto", weekday=1, time=time(9, 0))
        ms = MonthlySchedule(date=date(2026, 7, 12), schedule_type=st, member=m)
        ms.save()

        assert ms.year == 2026
        assert ms.month == 7

    def test_save_updates_year_month_on_date_change(self) -> None:
        m = Member.objects.create(name="Dave")
        st = ScheduleType.objects.create(name="Culto", weekday=1, time=time(9, 0))
        ms = MonthlySchedule.objects.create(date=date(2026, 5, 3), schedule_type=st, member=m)
        assert ms.month == 5

        ms.date = date(2026, 8, 10)
        ms.save()
        ms.refresh_from_db()

        assert ms.year == 2026
        assert ms.month == 8
