from datetime import date

import pytest
from rest_framework.test import APIClient

from conftest import make_auth_client, make_member_client, make_user
from features.members.models.member import Member


ENDPOINT = "/api/members/birthdays/"


@pytest.mark.django_db
class TestMemberBirthdaysAPIView:
    # --- Single month (backward compatibility) ---

    def test_single_month_returns_birthdays(self) -> None:
        Member.objects.create(name="Alice", birth_date=date(1990, 7, 5), gender="F", is_active=True)
        Member.objects.create(name="Bob", birth_date=date(1985, 7, 23), gender="M", is_active=True)
        Member.objects.create(name="Carol", birth_date=date(1992, 8, 10), is_active=True)
        client, _ = make_member_client()

        resp = client.get(ENDPOINT, {"month": 7})

        assert resp.status_code == 200
        birthdays = resp.data["birthdays"]
        assert len(birthdays) == 2
        assert birthdays[0]["name"] == "Alice"
        assert birthdays[0]["gender"] == "F"
        assert birthdays[0]["birth_month"] == 7
        assert birthdays[0]["birth_day"] == 5
        assert birthdays[1]["name"] == "Bob"
        assert birthdays[1]["gender"] == "M"
        assert birthdays[1]["birth_month"] == 7
        assert birthdays[1]["birth_day"] == 23

    def test_fields_unchanged_with_a_leader_only_photo(self) -> None:
        # Regression for feature 010: the leader-only photo must not leak into birthdays.
        Member.objects.create(name="Alice", birth_date=date(1990, 7, 5), photo="members/a.jpg")
        client, _ = make_member_client()

        resp = client.get(ENDPOINT, {"month": 7})

        assert set(resp.data["birthdays"][0]) == {"name", "gender", "birth_month", "birth_day"}

    def test_single_month_returns_birth_month_field(self) -> None:
        Member.objects.create(name="Alice", birth_date=date(1990, 7, 5), is_active=True)
        client, _ = make_member_client()

        resp = client.get(ENDPOINT, {"month": 7})

        assert resp.status_code == 200
        assert resp.data["birthdays"][0]["birth_month"] == 7

    def test_empty_month_returns_empty_list(self) -> None:
        Member.objects.create(name="Alice", birth_date=date(1990, 7, 5), is_active=True)
        client, _ = make_member_client()

        resp = client.get(ENDPOINT, {"month": 2})

        assert resp.status_code == 200
        assert resp.data["birthdays"] == []

    def test_null_gender_returned_as_null(self) -> None:
        Member.objects.create(
            name="NoGender", birth_date=date(1990, 7, 5), gender=None, is_active=True
        )
        client, _ = make_member_client()

        resp = client.get(ENDPOINT, {"month": 7})

        assert resp.status_code == 200
        assert resp.data["birthdays"][0]["gender"] is None

    def test_excludes_null_birth_date(self) -> None:
        Member.objects.create(name="Alice", birth_date=date(1990, 7, 5), is_active=True)
        Member.objects.create(name="NoBirthday", birth_date=None, is_active=True)
        client, _ = make_member_client()

        resp = client.get(ENDPOINT, {"month": 7})

        names = [b["name"] for b in resp.data["birthdays"]]
        assert "Alice" in names
        assert "NoBirthday" not in names

    def test_excludes_inactive_members(self) -> None:
        Member.objects.create(name="Active", birth_date=date(1990, 7, 5), is_active=True)
        Member.objects.create(name="Inactive", birth_date=date(1990, 7, 10), is_active=False)
        client, _ = make_member_client()

        resp = client.get(ENDPOINT, {"month": 7})

        names = [b["name"] for b in resp.data["birthdays"]]
        assert "Active" in names
        assert "Inactive" not in names

    def test_single_month_orders_by_day_ascending(self) -> None:
        Member.objects.create(name="Late", birth_date=date(1990, 3, 28), is_active=True)
        Member.objects.create(name="Early", birth_date=date(1995, 3, 3), is_active=True)
        Member.objects.create(name="Mid", birth_date=date(1988, 3, 15), is_active=True)
        client, _ = make_member_client()

        resp = client.get(ENDPOINT, {"month": 3})

        days = [b["birth_day"] for b in resp.data["birthdays"]]
        assert days == [3, 15, 28]

    def test_leading_zero_month_accepted(self) -> None:
        Member.objects.create(name="Alice", birth_date=date(1990, 7, 5), is_active=True)
        client, _ = make_member_client()

        resp = client.get(ENDPOINT, {"month": "07"})

        assert resp.status_code == 200
        assert len(resp.data["birthdays"]) == 1

    # --- Month range ---

    def test_range_returns_birthdays_across_months(self) -> None:
        Member.objects.create(name="Jan", birth_date=date(1990, 1, 15), is_active=True)
        Member.objects.create(name="Mar", birth_date=date(1985, 3, 10), is_active=True)
        Member.objects.create(name="Jun", birth_date=date(1992, 6, 20), is_active=True)
        Member.objects.create(name="Jul", birth_date=date(1988, 7, 5), is_active=True)
        client, _ = make_member_client()

        resp = client.get(ENDPOINT, {"month": "1-6"})

        assert resp.status_code == 200
        birthdays = resp.data["birthdays"]
        assert len(birthdays) == 3
        names = [b["name"] for b in birthdays]
        assert "Jan" in names
        assert "Mar" in names
        assert "Jun" in names
        assert "Jul" not in names

    def test_range_orders_by_month_then_day(self) -> None:
        Member.objects.create(name="Mar10", birth_date=date(1990, 3, 10), is_active=True)
        Member.objects.create(name="Jan20", birth_date=date(1985, 1, 20), is_active=True)
        Member.objects.create(name="Jan5", birth_date=date(1992, 1, 5), is_active=True)
        Member.objects.create(name="Mar1", birth_date=date(1988, 3, 1), is_active=True)
        client, _ = make_member_client()

        resp = client.get(ENDPOINT, {"month": "1-6"})

        assert resp.status_code == 200
        result = [(b["birth_month"], b["birth_day"]) for b in resp.data["birthdays"]]
        assert result == [(1, 5), (1, 20), (3, 1), (3, 10)]

    def test_range_full_year_returns_all(self) -> None:
        Member.objects.create(name="Jan", birth_date=date(1990, 1, 1), is_active=True)
        Member.objects.create(name="Dec", birth_date=date(1990, 12, 31), is_active=True)
        client, _ = make_member_client()

        resp = client.get(ENDPOINT, {"month": "1-12"})

        assert resp.status_code == 200
        assert len(resp.data["birthdays"]) == 2

    def test_range_excludes_members_outside_range(self) -> None:
        Member.objects.create(name="InRange", birth_date=date(1990, 3, 15), is_active=True)
        Member.objects.create(name="OutRange", birth_date=date(1990, 7, 10), is_active=True)
        client, _ = make_member_client()

        resp = client.get(ENDPOINT, {"month": "1-6"})

        names = [b["name"] for b in resp.data["birthdays"]]
        assert "InRange" in names
        assert "OutRange" not in names

    def test_range_same_month_equals_single(self) -> None:
        Member.objects.create(name="Alice", birth_date=date(1990, 7, 5), is_active=True)
        Member.objects.create(name="Bob", birth_date=date(1985, 7, 23), is_active=True)
        client, _ = make_member_client()

        resp_single = client.get(ENDPOINT, {"month": "7"})
        resp_range = client.get(ENDPOINT, {"month": "7-7"})

        assert resp_single.status_code == 200
        assert resp_range.status_code == 200
        assert resp_single.data["birthdays"] == resp_range.data["birthdays"]

    def test_range_empty_returns_empty_list(self) -> None:
        Member.objects.create(name="Alice", birth_date=date(1990, 7, 5), is_active=True)
        client, _ = make_member_client()

        resp = client.get(ENDPOINT, {"month": "1-3"})

        assert resp.status_code == 200
        assert resp.data["birthdays"] == []

    def test_range_with_leading_zeros(self) -> None:
        Member.objects.create(name="Alice", birth_date=date(1990, 1, 5), is_active=True)
        client, _ = make_member_client()

        resp = client.get(ENDPOINT, {"month": "01-06"})

        assert resp.status_code == 200
        assert len(resp.data["birthdays"]) == 1

    # --- Validation errors ---

    def test_missing_month_returns_400(self) -> None:
        client, _ = make_member_client()

        resp = client.get(ENDPOINT)

        assert resp.status_code == 400
        assert "month" in resp.data

    def test_start_greater_than_end_returns_400(self) -> None:
        client, _ = make_member_client()

        resp = client.get(ENDPOINT, {"month": "6-1"})

        assert resp.status_code == 400
        assert "month" in resp.data

    def test_out_of_range_zero_returns_400(self) -> None:
        client, _ = make_member_client()

        resp = client.get(ENDPOINT, {"month": "0-13"})

        assert resp.status_code == 400

    def test_out_of_range_thirteen_returns_400(self) -> None:
        client, _ = make_member_client()

        resp = client.get(ENDPOINT, {"month": 13})

        assert resp.status_code == 400

    def test_negative_month_returns_400(self) -> None:
        client, _ = make_member_client()

        resp = client.get(ENDPOINT, {"month": -1})

        assert resp.status_code == 400

    def test_non_numeric_returns_400(self) -> None:
        client, _ = make_member_client()

        resp = client.get(ENDPOINT, {"month": "abc"})

        assert resp.status_code == 400

    def test_non_numeric_range_returns_400(self) -> None:
        client, _ = make_member_client()

        resp = client.get(ENDPOINT, {"month": "a-b"})

        assert resp.status_code == 400

    def test_malformed_range_returns_400(self) -> None:
        client, _ = make_member_client()

        resp = client.get(ENDPOINT, {"month": "1-2-3"})

        assert resp.status_code == 400

    # --- Auth ---

    def test_unauthenticated_returns_401(self) -> None:
        resp = APIClient().get(ENDPOINT, {"month": 7})

        assert resp.status_code == 401

    def test_non_member_returns_403(self) -> None:
        user = make_user(username="regular")
        client = make_auth_client(user)

        resp = client.get(ENDPOINT, {"month": 7})

        assert resp.status_code == 403
