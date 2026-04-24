import pytest
from datetime import date, time, timedelta
from unittest.mock import patch

from django.utils import timezone
from rest_framework.test import APIClient

from features.members.models.member import Member
from features.schedule.models.schedule import (
    MemberScheduleConfig,
    MonthlySchedule,
    ScheduleType,
)
from tests.conftest import make_admin_client, make_member_client, make_user, make_auth_client


# --- Helpers ---


def make_schedule_type(
    name: str = "Culto", weekday: int = 1, time_str: str = "09:00"
) -> ScheduleType:
    h, m = map(int, time_str.split(":"))
    return ScheduleType.objects.create(name=name, weekday=weekday, time=time(h, m))


def make_member(name: str = "Alice") -> Member:
    return Member.objects.create(name=name)


def make_config(
    member: Member, schedule_type: ScheduleType, available: bool = True, weight: int = 1
) -> MemberScheduleConfig:
    return MemberScheduleConfig.objects.create(
        member=member, schedule_type=schedule_type, available=available, weight=weight
    )


# =====================================================================
# CurrentMonthlyScheduleAPI
# =====================================================================


@pytest.mark.django_db
class TestCurrentMonthlyScheduleAPIPermissions:
    ENDPOINT = "/api/schedule/current/"

    def test_unauthenticated_returns_401(self) -> None:
        resp = APIClient().get(self.ENDPOINT)
        assert resp.status_code == 401

    def test_non_member_returns_403(self) -> None:
        user = make_user(username="nonmember")
        client = make_auth_client(user)
        resp = client.get(self.ENDPOINT)
        assert resp.status_code == 403

    def test_member_returns_200(self) -> None:
        client, _ = make_member_client()
        resp = client.get(self.ENDPOINT)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestCurrentMonthlyScheduleAPI:
    ENDPOINT = "/api/schedule/current/"

    def test_returns_year_and_month(self) -> None:
        today = date.today()
        client, _ = make_member_client()
        resp = client.get(self.ENDPOINT)

        assert resp.data["year"] == today.year
        assert resp.data["month"] == today.month

    def test_returns_schedule_grouped_by_type(self) -> None:
        today = date.today()
        st = make_schedule_type("Culto")
        m = make_member("Alice")
        MonthlySchedule.objects.create(date=today, schedule_type=st, member=m)

        client, _ = make_member_client()
        resp = client.get(self.ENDPOINT)

        assert "Culto" in resp.data["schedule"]
        items = resp.data["schedule"]["Culto"]["items"]
        assert len(items) == 1
        assert items[0]["member"]["name"] == "Alice"

    def test_etag_304(self) -> None:
        client, _ = make_member_client()
        resp1 = client.get(self.ENDPOINT)
        etag = resp1["ETag"]
        resp2 = client.get(self.ENDPOINT, HTTP_IF_NONE_MATCH=etag)
        assert resp2.status_code == 304

    def test_empty_schedule(self) -> None:
        client, _ = make_member_client()
        resp = client.get(self.ENDPOINT)
        assert resp.data["schedule"] == {}


# =====================================================================
# MonthlySchedulePreviewAPI
# =====================================================================


@pytest.mark.django_db
class TestMonthlySchedulePreviewAPI:
    ENDPOINT = "/api/schedule/generate/"

    def test_unauthenticated_returns_401(self) -> None:
        resp = APIClient().post(self.ENDPOINT, {}, format="json")
        assert resp.status_code == 401

    def test_non_admin_returns_403(self) -> None:
        client, _ = make_member_client()
        resp = client.post(self.ENDPOINT, {}, format="json")
        assert resp.status_code == 403

    def test_admin_returns_200_with_preview(self) -> None:
        st = make_schedule_type(weekday=1)
        m = make_member("Bob")
        make_config(m, st)
        client, _ = make_admin_client()

        resp = client.post(self.ENDPOINT, {"year": 2026, "month": 5}, format="json")

        assert resp.status_code == 200
        assert resp.data["year"] == 2026
        assert resp.data["month"] == 5
        assert isinstance(resp.data["items"], list)

    def test_defaults_to_next_month_when_omitted(self) -> None:
        st = make_schedule_type(weekday=1)
        m = make_member()
        make_config(m, st)
        client, _ = make_admin_client()

        real_date = date
        with patch("features.schedule.services.monthly_scheduler.date") as mock_date:
            mock_date.today.return_value = real_date(2026, 4, 15)
            mock_date.side_effect = lambda *a, **kw: real_date(*a, **kw)

            resp = client.post(self.ENDPOINT, {}, format="json")

        assert resp.status_code == 200
        assert resp.data["year"] == 2026
        assert resp.data["month"] == 5

    def test_fixed_param_applied(self) -> None:
        st = make_schedule_type(weekday=1)
        m1 = make_member("M1")
        m2 = make_member("M2")
        make_config(m1, st, weight=5)
        make_config(m2, st, weight=5)
        client, _ = make_admin_client()

        fixed_date = "2026-05-03"
        resp = client.post(
            self.ENDPOINT,
            {
                "year": 2026,
                "month": 5,
                "fixed": [
                    {
                        "schedule_type_id": st.id,
                        "date": fixed_date,
                        "member_id": m2.id,
                    }
                ],
            },
            format="json",
        )

        assert resp.status_code == 200
        fixed_items = [i for i in resp.data["items"] if i["date"] == fixed_date]
        assert len(fixed_items) == 1
        assert fixed_items[0]["member"]["id"] == m2.id
        assert fixed_items[0]["fixed"] is True

    def test_invalid_fixed_entries_skipped(self) -> None:
        st = make_schedule_type(weekday=1)
        m = make_member()
        make_config(m, st)
        client, _ = make_admin_client()

        resp = client.post(
            self.ENDPOINT,
            {
                "year": 2026,
                "month": 5,
                "fixed": [{"bad": "data"}, "not_a_dict"],
            },
            format="json",
        )

        assert resp.status_code == 200


# =====================================================================
# MonthlyScheduleSaveAPI
# =====================================================================


@pytest.mark.django_db
class TestMonthlyScheduleSaveAPI:
    ENDPOINT = "/api/schedule/save/"

    def test_unauthenticated_returns_401(self) -> None:
        resp = APIClient().post(self.ENDPOINT, {}, format="json")
        assert resp.status_code == 401

    def test_non_admin_returns_403(self) -> None:
        client, _ = make_member_client()
        resp = client.post(self.ENDPOINT, {}, format="json")
        assert resp.status_code == 403

    def test_admin_saves_schedule(self) -> None:
        st = make_schedule_type()
        m = make_member("Alice")
        client, _ = make_admin_client()

        resp = client.post(
            self.ENDPOINT,
            {
                "year": 2026,
                "month": 5,
                "items": [
                    {
                        "date": "2026-05-03",
                        "schedule_type_id": st.id,
                        "member_id": m.id,
                    },
                    {
                        "date": "2026-05-10",
                        "schedule_type_id": st.id,
                        "member_id": m.id,
                    },
                ],
            },
            format="json",
        )

        assert resp.status_code == 200
        assert resp.data["ok"] is True
        assert MonthlySchedule.objects.filter(year=2026, month=5).count() == 2

    def test_saves_with_nested_format(self) -> None:
        st = make_schedule_type()
        m = make_member("Bob")
        client, _ = make_admin_client()

        resp = client.post(
            self.ENDPOINT,
            {
                "year": 2026,
                "month": 5,
                "items": [
                    {
                        "date": "2026-05-03",
                        "schedule_type": {"id": st.id, "name": st.name},
                        "member": {"id": m.id, "name": m.name},
                    }
                ],
            },
            format="json",
        )

        assert resp.status_code == 200
        assert MonthlySchedule.objects.filter(year=2026, month=5).count() == 1

    def test_missing_year_returns_500(self) -> None:
        client, _ = make_admin_client()
        resp = client.post(self.ENDPOINT, {"month": 5, "items": []}, format="json")
        assert resp.status_code == 500

    def test_save_after_30_minutes_returns_400(self) -> None:
        st = make_schedule_type()
        m = make_member()
        client, _ = make_admin_client()

        MonthlySchedule.objects.create(date=date(2026, 5, 3), schedule_type=st, member=m)
        MonthlySchedule.objects.filter(year=2026, month=5).update(
            created_at=timezone.now() - timedelta(minutes=31)
        )

        resp = client.post(
            self.ENDPOINT,
            {
                "year": 2026,
                "month": 5,
                "items": [
                    {
                        "date": "2026-05-03",
                        "schedule_type_id": st.id,
                        "member_id": m.id,
                    }
                ],
            },
            format="json",
        )

        assert resp.status_code == 400
        assert "30 minutos" in resp.data["error"]

    def test_empty_items_clears_nothing(self) -> None:
        client, _ = make_admin_client()

        resp = client.post(
            self.ENDPOINT,
            {"year": 2026, "month": 5, "items": []},
            format="json",
        )

        assert resp.status_code == 200
        assert MonthlySchedule.objects.filter(year=2026, month=5).count() == 0

    def test_malformed_items_skipped(self) -> None:
        st = make_schedule_type()
        m = make_member()
        client, _ = make_admin_client()

        resp = client.post(
            self.ENDPOINT,
            {
                "year": 2026,
                "month": 5,
                "items": [
                    {"bad": "data"},
                    {
                        "date": "2026-05-03",
                        "schedule_type_id": st.id,
                        "member_id": m.id,
                    },
                ],
            },
            format="json",
        )

        assert resp.status_code == 200
        assert MonthlySchedule.objects.filter(year=2026, month=5).count() == 1
