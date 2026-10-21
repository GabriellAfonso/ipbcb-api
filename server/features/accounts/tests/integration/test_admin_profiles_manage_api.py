"""US3 — revoke, block, link (specs/022-access-requests contracts/access-api.md)."""

from collections.abc import Iterator

import pytest
from dependency_injector import providers
from rest_framework.test import APIClient

from config.di import Container
from conftest import make_auth_client, make_member_client, make_role_client, make_user
from core.domain.access import Role
from core.tests.fakes import FakePushSender
from features.accounts.tests.integration.access_helpers import (
    ME_REQUESTS_URL,
    PROFILE_URL,
    account_url,
    register_device,
)
from features.members.models.member import Member

pytestmark = pytest.mark.django_db

BIRTHDAYS_URL = "/api/members/birthdays/?month=1"


@pytest.fixture
def sender(di_container: Container) -> Iterator[FakePushSender]:
    fake = FakePushSender()
    with di_container.push_sender.override(providers.Object(fake)):
        yield fake


@pytest.fixture
def leader() -> APIClient:
    return make_role_client(Role.LEADER, username="leader")[0]


class TestRevoke:
    def test_revoked_member_loses_content_and_gets_no_push(
        self, leader: APIClient, sender: FakePushSender
    ) -> None:
        member_client, member = make_member_client()
        register_device(member, "t-member")
        assert member_client.get(BIRTHDAYS_URL).status_code == 200

        response = leader.post(account_url(member, "revoke-access/"))

        assert response.status_code == 200
        assert response.data["member_access"] is False
        assert member_client.get(BIRTHDAYS_URL).status_code == 403
        assert member_client.get(PROFILE_URL).data["access_status"] == "none"
        assert sender.calls == []

    def test_unknown_account(self, leader: APIClient) -> None:
        url = "/api/admin/profiles/00000000-0000-0000-0000-000000000001/revoke-access/"
        assert leader.post(url).status_code == 404


class TestBlock:
    def test_block_and_unblock(self, leader: APIClient, sender: FakePushSender) -> None:
        user = make_user(username="ana")
        client = make_auth_client(user)

        blocked = leader.patch(account_url(user), {"access_requests_blocked": True}, format="json")
        assert blocked.data["access_requests_blocked"] is True
        assert client.get(PROFILE_URL).data["access_requests_blocked"] is True
        refused = client.post(ME_REQUESTS_URL, {"type": "access"}, format="json")
        assert refused.data["error_code"] == "ACCESS_REQUESTS_BLOCKED"

        leader.patch(account_url(user), {"access_requests_blocked": False}, format="json")
        accepted = client.post(ME_REQUESTS_URL, {"type": "access"}, format="json")
        assert accepted.status_code == 201

    def test_unknown_field(self, leader: APIClient) -> None:
        user = make_user(username="ana")
        response = leader.patch(account_url(user), {"blocked": True}, format="json")
        assert response.status_code == 400

    def test_email_is_not_accepted(self, leader: APIClient) -> None:
        # Google sign-in links accounts by e-mail: no endpoint here may change it (spec FR-019).
        user = make_user(username="ana", email="ana@example.com")
        response = leader.patch(account_url(user), {"email": "x@example.com"}, format="json")
        assert response.status_code == 400
        user.refresh_from_db()
        assert user.email == "ana@example.com"


class TestLink:
    def test_link_and_unlink(self, leader: APIClient) -> None:
        user = make_user(username="ana")
        member = Member.objects.create(name="Ana Souza")

        linked = leader.patch(account_url(user), {"member_id": member.pk}, format="json")
        assert linked.data["member"] == {"id": member.pk, "name": "Ana Souza"}
        assert make_auth_client(user).get(PROFILE_URL).data["member_id"] == member.pk

        unlinked = leader.patch(account_url(user), {"member_id": None}, format="json")
        assert unlinked.data["member"] is None
        assert Member.objects.filter(pk=member.pk).exists()

    def test_member_of_another_account_is_a_conflict(self, leader: APIClient) -> None:
        member = Member.objects.create(name="Ana Souza")
        first = make_user(username="first")
        second = make_user(username="second")
        leader.patch(account_url(first), {"member_id": member.pk}, format="json")

        response = leader.patch(account_url(second), {"member_id": member.pk}, format="json")

        assert response.status_code == 409
        assert response.data["error_code"] == "MEMBER_ALREADY_LINKED"
        second.profile.refresh_from_db()
        assert second.profile.member_id is None

    def test_unknown_member(self, leader: APIClient) -> None:
        response = leader.patch(
            account_url(make_user(username="ana")), {"member_id": 999}, format="json"
        )
        assert response.status_code == 400
        assert "member_id" in response.data["field_errors"]

    def test_link_does_not_change_access(self, leader: APIClient) -> None:
        user = make_user(username="ana")
        member = Member.objects.create(name="Ana Souza")
        response = leader.patch(account_url(user), {"member_id": member.pk}, format="json")
        assert response.data["member_access"] is False
