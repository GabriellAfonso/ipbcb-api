import pytest
from rest_framework.test import APIClient

from features.members.models.member import Member
from conftest import make_auth_client, make_member_client, make_role_client, make_user
from core.domain.access import Role


ENDPOINT = "/api/members/"


@pytest.mark.django_db
class TestMemberListAPIView:
    def test_unauthenticated_returns_401(self) -> None:
        resp = APIClient().get(ENDPOINT)
        assert resp.status_code == 401

    def test_non_member_returns_403(self) -> None:
        user = make_user(username="regular")
        client = make_auth_client(user)
        resp = client.get(ENDPOINT)
        assert resp.status_code == 403

    @pytest.mark.parametrize("role", [Role.LEADER, Role.ADMIN])
    def test_schedule_role_without_membership_returns_active_members(self, role: Role) -> None:
        # specs/012-feature-role-permissions FR-031: the schedule screen loads this list.
        Member.objects.create(name="Active", is_active=True)
        Member.objects.create(name="Inactive", is_active=False)
        client, _ = make_role_client(role)

        resp = client.get(ENDPOINT)

        assert resp.status_code == 200
        assert [m["name"] for m in resp.data["members"]] == ["Active"]

    def test_media_role_without_membership_returns_403(self) -> None:
        client, _ = make_role_client(Role.MEDIA)
        assert client.get(ENDPOINT).status_code == 403

    def test_media_role_with_membership_returns_200(self) -> None:
        client, user = make_role_client(Role.MEDIA)
        user.profile.is_member = True
        user.profile.save()
        assert client.get(ENDPOINT).status_code == 200

    def test_member_returns_200(self) -> None:
        Member.objects.create(name="Alice", is_active=True)
        client, _ = make_member_client()

        resp = client.get(ENDPOINT)

        assert resp.status_code == 200
        assert len(resp.data["members"]) == 1
        assert resp.data["members"][0]["name"] == "Alice"

    def test_returns_only_active_members(self) -> None:
        Member.objects.create(name="Active", is_active=True)
        Member.objects.create(name="Inactive", is_active=False)
        client, _ = make_member_client()

        resp = client.get(ENDPOINT)

        names = [m["name"] for m in resp.data["members"]]
        assert "Active" in names
        assert "Inactive" not in names

    def test_ordered_by_name(self) -> None:
        Member.objects.create(name="Zara", is_active=True)
        Member.objects.create(name="Ana", is_active=True)
        Member.objects.create(name="Marco", is_active=True)
        client, _ = make_member_client()

        resp = client.get(ENDPOINT)

        names = [m["name"] for m in resp.data["members"]]
        assert names == sorted(names)

    def test_response_contains_id_and_name(self) -> None:
        Member.objects.create(name="Bob", is_active=True)
        client, _ = make_member_client()

        resp = client.get(ENDPOINT)

        member_data = resp.data["members"][0]
        assert "id" in member_data
        assert "name" in member_data

    def test_empty_list_when_no_active_members(self) -> None:
        client, _ = make_member_client()

        resp = client.get(ENDPOINT)

        assert resp.status_code == 200
        assert resp.data["members"] == []

    def test_exactly_id_and_name_even_with_a_leader_only_photo(self) -> None:
        # Regression for feature 010: the leader-only photo must not leak into this list.
        Member.objects.create(name="Bob", is_active=True, photo="members/abc.jpg")
        client, _ = make_member_client()

        resp = client.get(ENDPOINT)

        assert set(resp.data["members"][0]) == {"id", "name"}
