"""Leader roll endpoints: list, detail, options, create, edit, delete
(specs/010-members-management/contracts/admin-members-api.md; birth date parts:
specs/011-split-birth-date/contracts/admin-members-api.md)."""

import logging

import pytest
from rest_framework.test import APIClient

from conftest import make_admin_client, make_auth_client, make_member_client, make_user
from features.members.models.member import Member, MemberStatus, Ministry, Role
from features.members.models.member_change_log import MemberChangeLog

LIST_URL = "/api/admin/members/"
OPTIONS_URL = "/api/admin/members/options/"


def detail_url(member_id: int) -> str:
    return f"/api/admin/members/{member_id}/"


SUMMARY_FIELDS = {"id", "name", "photo_url", "status", "is_active"}
RECORD_FIELDS = {
    "id",
    "name",
    "first_name",
    "last_name",
    "birth_day",
    "birth_month",
    "birth_year",
    "gender",
    "status",
    "role",
    "ministries",
    "baptism_date",
    "is_active",
    "photo_url",
    "created_at",
}


def _no_profile_client() -> APIClient:
    user = make_user(username="ghost")
    user.profile.delete()
    return make_auth_client(user)


@pytest.mark.django_db
class TestAccess:
    @pytest.mark.parametrize("method", ["get", "post"])
    def test_anonymous_gets_401(self, method: str) -> None:
        response = getattr(APIClient(), method)(LIST_URL)
        assert response.status_code == 401

    @pytest.mark.parametrize(
        ("method", "url"),
        [
            ("get", LIST_URL),
            ("post", LIST_URL),
            ("get", OPTIONS_URL),
            ("get", "/api/admin/members/1/"),
            ("patch", "/api/admin/members/1/"),
            ("delete", "/api/admin/members/1/"),
        ],
    )
    def test_plain_member_gets_403_and_no_data(self, method: str, url: str) -> None:
        Member.objects.create(pk=1, name="Maria Sigilo")
        client, _ = make_member_client()

        response = getattr(client, method)(url, {"name": "X"}, format="json")

        assert response.status_code == 403
        assert response.data["error_code"] == "PERMISSION_DENIED"
        assert "Maria" not in response.content.decode()
        assert Member.objects.get(pk=1).name == "Maria Sigilo"

    def test_user_without_profile_gets_403(self) -> None:
        assert _no_profile_client().get(LIST_URL).status_code == 403


@pytest.mark.django_db
class TestList:
    def test_every_member_with_exact_fields(self) -> None:
        status = MemberStatus.objects.create(name="Comungante")
        Member.objects.create(name="Bruno", is_active=False)
        Member.objects.create(name="Ana", status=status)
        client, _ = make_admin_client()

        response = client.get(LIST_URL)

        assert response.status_code == 200
        members = response.data["members"]
        assert [m["name"] for m in members] == ["Ana", "Bruno"]
        assert all(set(m) == SUMMARY_FIELDS for m in members)
        assert members[0]["status"] == {"id": status.pk, "name": "Comungante"}
        assert members[1]["is_active"] is False
        assert members[1]["photo_url"] is None

    def test_private_cache_and_304(self) -> None:
        Member.objects.create(name="Ana")
        client, _ = make_admin_client()

        first = client.get(LIST_URL)
        second = client.get(LIST_URL, HTTP_IF_NONE_MATCH=first["ETag"])

        assert first["Cache-Control"] == "private, no-store"
        assert "Authorization" in first["Vary"]
        assert second.status_code == 304


@pytest.mark.django_db
class TestDetail:
    def test_full_record(self) -> None:
        member = Member.objects.create(
            name="Ana",
            gender="F",
            birth_day=2,
            birth_month=4,
            birth_year=1990,
            photo="members/abc.jpg",
        )
        member.ministries.set([Ministry.objects.create(name="Louvor")])
        client, _ = make_admin_client()

        response = client.get(detail_url(member.pk))

        assert response.status_code == 200
        assert set(response.data) == RECORD_FIELDS
        assert (response.data["birth_day"], response.data["birth_month"]) == (2, 4)
        assert response.data["birth_year"] == 1990
        assert response.data["ministries"][0]["name"] == "Louvor"
        assert response.data["photo_url"] == "http://testserver/ipbcb/media/members/abc.jpg"
        assert response["Cache-Control"] == "private, no-store"

    def test_unknown_id_404(self) -> None:
        client, _ = make_admin_client()

        response = client.get(detail_url(999))

        assert response.status_code == 404
        assert response.data["error_code"] == "NOT_FOUND"

    def test_304_when_unchanged(self) -> None:
        member = Member.objects.create(name="Ana")
        client, _ = make_admin_client()

        first = client.get(detail_url(member.pk))
        second = client.get(detail_url(member.pk), HTTP_IF_NONE_MATCH=first["ETag"])

        assert second.status_code == 304


@pytest.mark.django_db
class TestOptions:
    def test_three_lists_ordered_by_name(self) -> None:
        MemberStatus.objects.create(name="Não comungante")
        MemberStatus.objects.create(name="Comungante")
        role = Role.objects.create(name="Diácono")
        Ministry.objects.create(name="Louvor")
        client, _ = make_admin_client()

        response = client.get(OPTIONS_URL)

        assert response.status_code == 200
        assert [s["name"] for s in response.data["statuses"]] == ["Comungante", "Não comungante"]
        assert response.data["roles"] == [{"id": role.pk, "name": "Diácono"}]
        assert [m["name"] for m in response.data["ministries"]] == ["Louvor"]
        assert response["Cache-Control"] == "private, no-store"


@pytest.mark.django_db
class TestCreate:
    def test_creates_with_references_and_history(self) -> None:
        status = MemberStatus.objects.create(name="Comungante")
        louvor = Ministry.objects.create(name="Louvor")
        client, leader = make_admin_client()

        response = client.post(
            LIST_URL,
            {"name": "Ana Souza", "status_id": status.pk, "ministry_ids": [louvor.pk]},
            format="json",
        )

        assert response.status_code == 201
        assert set(response.data) == RECORD_FIELDS
        assert response.data["is_active"] is True
        assert response.data["status"] == {"id": status.pk, "name": "Comungante"}
        (entry,) = MemberChangeLog.objects.filter(member_id=response.data["id"])
        assert (entry.field, entry.editor_id) == ("created", leader.pk)

    @pytest.mark.parametrize(
        "body",
        [
            {},
            {"name": ""},
            {"name": "Ana", "gender": "X"},
            {"name": "Ana", "status_id": "abc"},
            {"name": "Ana", "status_id": 999},
            {"name": "Ana", "ministry_ids": [999]},
            {"name": "Ana", "birth_year": 2999},
            {"name": "Ana", "birth_date": "1990-01-01"},
            {"name": "Ana", "photo": "members/x.jpg"},
            {"name": "Ana", "id": 5},
            {"name": "Ana", "created_at": "2020-01-01T00:00:00Z"},
        ],
    )
    def test_invalid_body_400_and_nothing_stored(self, body: dict[str, object]) -> None:
        client, _ = make_admin_client()

        response = client.post(LIST_URL, body, format="json")

        assert response.status_code == 400
        assert response.data["error_code"] == "VALIDATION_ERROR"
        assert not Member.objects.exists()
        assert not MemberChangeLog.objects.exists()

    def test_non_object_body_400(self) -> None:
        client, _ = make_admin_client()

        response = client.post(LIST_URL, ["Ana"], format="json")

        assert response.status_code == 400
        assert response.data["error_code"] == "VALIDATION_ERROR"


@pytest.mark.django_db
class TestPatch:
    def test_partial_update_and_history(self) -> None:
        status = MemberStatus.objects.create(name="Comungante")
        member = Member.objects.create(
            name="Ana", gender="F", birth_day=2, birth_month=4, birth_year=1990
        )
        client, _ = make_admin_client()

        response = client.patch(
            detail_url(member.pk),
            {"status_id": status.pk, "birth_year": 1991},
            format="json",
        )

        assert response.status_code == 200
        assert response.data["gender"] == "F"
        assert response.data["birth_year"] == 1991
        rows = MemberChangeLog.objects.filter(member=member).values_list(
            "field", "old_value", "new_value"
        )
        assert set(rows) == {
            ("birth_year", "1990", "1991"),
            ("status", None, "Comungante"),
        }

    def test_empty_body_writes_nothing(self) -> None:
        member = Member.objects.create(name="Ana")
        client, _ = make_admin_client()

        response = client.patch(detail_url(member.pk), {}, format="json")

        assert response.status_code == 200
        assert not MemberChangeLog.objects.exists()

    @pytest.mark.parametrize(
        "body",
        [{"name": None}, {"name": ""}, {"baptism_date": "1980-01-01"}, {"role_id": 999}],
    )
    def test_rejected_edit_changes_nothing(self, body: dict[str, object]) -> None:
        member = Member.objects.create(name="Ana", birth_day=2, birth_month=4, birth_year=1990)
        client, _ = make_admin_client()

        response = client.patch(detail_url(member.pk), body, format="json")

        assert response.status_code == 400
        member.refresh_from_db()
        assert (member.name, member.baptism_date, member.role_id) == ("Ana", None, None)
        assert not MemberChangeLog.objects.exists()

    def test_unknown_member_404(self) -> None:
        client, _ = make_admin_client()

        assert client.patch(detail_url(999), {"gender": "M"}, format="json").status_code == 404

    def test_invalid_profile_leaves_regular_lists_but_stays_for_leaders(self) -> None:
        member = Member.objects.create(name="Ana", birth_day=5, birth_month=7, birth_year=1990)
        leader_client, _ = make_admin_client()
        member_client, _ = make_member_client()

        leader_client.patch(detail_url(member.pk), {"is_active": False}, format="json")

        assert member_client.get("/api/members/").data["members"] == []
        birthdays = member_client.get("/api/members/birthdays/", {"month": "7"})
        assert birthdays.data["birthdays"] == []
        assert [m["name"] for m in leader_client.get(LIST_URL).data["members"]] == ["Ana"]


@pytest.mark.django_db
class TestLogHygiene:
    def test_write_logs_carry_no_member_data(self, caplog: pytest.LogCaptureFixture) -> None:
        # SC-006: member data is sensitive (LGPD art. 11); logs carry ids only.
        caplog.set_level(logging.INFO)
        client, _ = make_admin_client()

        member_id = client.post(
            LIST_URL,
            {"name": "Maria Sigilo", "birth_day": 14, "birth_month": 3, "birth_year": 1987},
            format="json",
        ).data["id"]
        client.patch(detail_url(member_id), {"last_name": "Reservada"}, format="json")
        client.delete(detail_url(member_id))

        logged = " ".join(str(record.__dict__) for record in caplog.records)
        assert "member_created" in logged and "member_deleted" in logged
        for secret in ("Maria", "Sigilo", "Reservada", "1987"):
            assert secret not in logged


@pytest.mark.django_db
class TestDelete:
    def test_deletes_member_and_history(self) -> None:
        member = Member.objects.create(name="Ana")
        MemberChangeLog.objects.create(member=member, field="created")
        client, _ = make_admin_client()

        response = client.delete(detail_url(member.pk))

        assert response.status_code == 204
        assert not Member.objects.exists()
        assert not MemberChangeLog.objects.exists()
        assert client.delete(detail_url(member.pk)).status_code == 404


@pytest.mark.django_db
class TestBirthDateParts:
    """Spec 011, US1: the leader stores exactly the parts that are known."""

    @pytest.mark.parametrize(
        "parts",
        [
            {"birth_day": 12, "birth_month": 3, "birth_year": 1990},
            {"birth_day": 12, "birth_month": 3, "birth_year": None},
            {"birth_day": None, "birth_month": None, "birth_year": 1950},
            {"birth_day": None, "birth_month": None, "birth_year": None},
        ],
    )
    def test_create_returns_the_parts_sent(self, parts: dict[str, int | None]) -> None:
        client, _ = make_admin_client()

        response = client.post(LIST_URL, {"name": "Ana", **parts}, format="json")

        assert response.status_code == 201
        assert {key: response.data[key] for key in parts} == parts

    def test_clearing_the_year_keeps_day_and_month(self) -> None:
        member = Member.objects.create(name="Ana", birth_day=12, birth_month=3, birth_year=1990)
        client, _ = make_admin_client()

        response = client.patch(detail_url(member.pk), {"birth_year": None}, format="json")

        assert response.status_code == 200
        assert (response.data["birth_day"], response.data["birth_month"]) == (12, 3)
        assert response.data["birth_year"] is None

    def test_adding_day_and_month_to_a_year(self) -> None:
        member = Member.objects.create(name="Ana", birth_year=1950)
        client, _ = make_admin_client()

        response = client.patch(
            detail_url(member.pk), {"birth_day": 5, "birth_month": 8}, format="json"
        )

        assert response.status_code == 200
        parts = (response.data["birth_day"], response.data["birth_month"])
        assert parts + (response.data["birth_year"],) == (5, 8, 1950)

    def test_old_birth_date_key_is_refused_by_name(self) -> None:
        client, _ = make_admin_client()

        response = client.post(LIST_URL, {"name": "Ana", "birth_date": "1990-01-01"}, format="json")

        assert response.status_code == 400
        assert response.data["error_code"] == "VALIDATION_ERROR"
        assert "birth_date" in str(response.data["field_errors"])


BIRTH_REJECTIONS = [
    ({"birth_day": 12}, "birth_day=12, birth_month=None"),
    ({"birth_day": 31, "birth_month": 4}, "31/04"),
    ({"birth_day": 29, "birth_month": 2, "birth_year": 1990}, "29/02/1990"),
    ({"birth_year": 2999}, "birth_year=2999"),
    ({"birth_year": 1990, "baptism_date": "1989-05-01"}, "1989-05-01"),
    ({"birth_day": 0, "birth_month": 3}, "birth_day=0"),
    ({"birth_day": 1, "birth_month": 13}, "birth_month=13"),
]


@pytest.mark.django_db
class TestBirthDateRejections:
    """Spec 011, US2: each invalid combination is refused naming the value, nothing stored."""

    @pytest.mark.parametrize(("parts", "offending"), BIRTH_REJECTIONS)
    def test_create_rejected_naming_the_value(
        self, parts: dict[str, object], offending: str
    ) -> None:
        client, _ = make_admin_client()

        response = client.post(LIST_URL, {"name": "Ana", **parts}, format="json")

        assert response.status_code == 400
        assert response.data["error_code"] == "VALIDATION_ERROR"
        assert offending in response.data["detail"]
        assert not Member.objects.exists()

    @pytest.mark.parametrize(("parts", "offending"), BIRTH_REJECTIONS)
    def test_patch_rejected_and_record_unchanged(
        self, parts: dict[str, object], offending: str
    ) -> None:
        member = Member.objects.create(name="Ana")
        client, _ = make_admin_client()

        response = client.patch(detail_url(member.pk), parts, format="json")

        assert response.status_code == 400
        assert offending in response.data["detail"]
        member.refresh_from_db()
        assert (member.birth_day, member.birth_month, member.birth_year) == (None, None, None)
        assert not MemberChangeLog.objects.exists()

    def test_non_integer_part_is_a_validation_error(self) -> None:
        client, _ = make_admin_client()

        response = client.post(LIST_URL, {"name": "Ana", "birth_day": "abc"}, format="json")

        assert response.status_code == 400
        assert response.data["error_code"] == "VALIDATION_ERROR"
