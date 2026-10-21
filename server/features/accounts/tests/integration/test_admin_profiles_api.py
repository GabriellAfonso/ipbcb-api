"""US2 — "Perfis": lists and decisions (specs/022-access-requests contracts/access-api.md)."""

from collections.abc import Iterator
from datetime import timedelta

import pytest
from dependency_injector import providers
from django.utils import timezone
from rest_framework.test import APIClient

from config.di import Container
from conftest import make_auth_client, make_member_client, make_role_client, make_user
from core.domain.access import Role
from core.tests.fakes import FakePushSender
from features.accounts.models.access_request import AccessRequest
from features.accounts.models.user import User
from features.accounts.tests.integration.access_helpers import (
    PROFILES_URL,
    account_url,
    decision_url,
    register_device,
    tokens_messaged,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def sender(di_container: Container) -> Iterator[FakePushSender]:
    fake = FakePushSender()
    with di_container.push_sender.override(providers.Object(fake)):
        yield fake


@pytest.fixture
def leader() -> APIClient:
    return make_role_client(Role.LEADER, username="leader")[0]


def _account(username: str, name: str) -> User:
    user = make_user(username=username)
    user.profile.name = name
    user.profile.save()
    return user


def _request(
    user: User, kind: str = "access", age_hours: int = 0, **fields: object
) -> AccessRequest:
    request = AccessRequest.objects.create(user=user, type=kind, **fields)
    created_at = timezone.now() - timedelta(hours=age_hours)
    AccessRequest.objects.filter(pk=request.pk).update(created_at=created_at)
    request.refresh_from_db()
    return request


class TestList:
    def test_pending_tab_oldest_first(self, leader: APIClient) -> None:
        newer = _account("newer", "Bruno")
        older = _account("older", "Carla")
        _account("idle", "Ana")
        _request(newer, age_hours=1)
        _request(older, age_hours=5)

        accounts = leader.get(PROFILES_URL, {"status": "pending"}).data["accounts"]

        assert [a["username"] for a in accounts] == ["older", "newer"]
        assert accounts[0]["pending_requests"][0]["type"] == "access"

    def test_all_tab_by_name_with_inactive_left_out(self, leader: APIClient) -> None:
        _account("zeca", "Zeca")
        _account("ana", "Ana")
        gone = _account("gone", "Bia")
        gone.is_active = False
        gone.save()

        accounts = leader.get(PROFILES_URL).data["accounts"]

        names = [a["name"] for a in accounts]
        assert "Bia" not in names
        assert names.index("Ana") < names.index("Zeca")

    def test_account_shape_has_no_email(self, leader: APIClient) -> None:
        member_client, member = make_member_client()
        account = next(
            a for a in leader.get(PROFILES_URL).data["accounts"] if a["id"] == str(member.pk)
        )
        assert set(account) == {
            "id",
            "name",
            "username",
            "photo_url",
            "member_access",
            "access_via_role",
            "access_requests_blocked",
            "member",
            "date_joined",
            "pending_requests",
        }
        assert account["member_access"] is True
        assert account["access_via_role"] is False

    def test_access_via_role(self, leader: APIClient) -> None:
        accounts = leader.get(PROFILES_URL).data["accounts"]
        me = next(a for a in accounts if a["username"] == "leader")
        assert me["member_access"] is False
        assert me["access_via_role"] is True

    def test_unknown_filter(self, leader: APIClient) -> None:
        response = leader.get(PROFILES_URL, {"status": "old"})
        assert response.status_code == 400
        assert "status" in response.data["field_errors"]

    def test_list_is_private(self, leader: APIClient) -> None:
        response = leader.get(PROFILES_URL)
        assert response["Cache-Control"] == "private, no-store"

    def test_queries_do_not_grow_with_accounts(
        self, leader: APIClient, django_assert_max_num_queries: object
    ) -> None:
        for index in range(6):
            _request(_account(f"user{index}", f"User {index}"))
        with django_assert_max_num_queries(8):  # type: ignore[operator]
            leader.get(PROFILES_URL)


class TestDetail:
    def test_history_newest_first(self, leader: APIClient) -> None:
        ana = _account("ana", "Ana")
        _request(ana, age_hours=48, status="denied", denial_reason="Procure o pastor.")
        _request(ana, kind="data_correction", message="x")

        detail = leader.get(account_url(ana)).data

        assert [r["type"] for r in detail["requests"]] == ["data_correction", "access"]
        assert detail["requests"][1]["denial_reason"] == "Procure o pastor."
        assert len(detail["pending_requests"]) == 1

    def test_unknown_account(self, leader: APIClient) -> None:
        response = leader.get(f"{PROFILES_URL}00000000-0000-0000-0000-000000000001/")
        assert response.status_code == 404


class TestDecisions:
    def test_approve_access_sets_the_flag_and_notifies(
        self, leader: APIClient, sender: FakePushSender
    ) -> None:
        ana = _account("ana", "Ana")
        register_device(ana, "t-ana")
        request = _request(ana)

        response = leader.post(decision_url(request.pk, "approve"))

        assert response.status_code == 200
        assert response.data["member_access"] is True
        decided = response.data["requests"][0]
        assert decided["status"] == "approved"
        assert decided["decided_by"]["name"] == ""
        assert decided["decided_at"] is not None
        ana.profile.refresh_from_db()
        assert ana.profile.member_access is True
        assert tokens_messaged(sender) == [
            (
                {"t-ana"},
                {
                    "type": "access_request_approved",
                    "request_id": str(request.pk),
                    "request_type": "access",
                },
            )
        ]

    def test_approve_correction_only_closes_it(
        self, leader: APIClient, sender: FakePushSender
    ) -> None:
        ana = _account("ana", "Ana")
        request = _request(ana, kind="data_correction", message="x")
        response = leader.post(decision_url(request.pk, "approve"))
        assert response.data["member_access"] is False
        assert response.data["requests"][0]["status"] == "approved"

    def test_deny_with_reason(self, leader: APIClient, sender: FakePushSender) -> None:
        ana = _account("ana", "Ana")
        register_device(ana, "t-ana")
        request = _request(ana)

        response = leader.post(
            decision_url(request.pk, "deny"), {"reason": " Procure o pastor. "}, format="json"
        )

        assert response.status_code == 200
        assert response.data["member_access"] is False
        assert response.data["requests"][0]["denial_reason"] == "Procure o pastor."
        [(_, payload)] = tokens_messaged(sender)
        assert payload["type"] == "access_request_denied"
        assert payload["reason"] == "Procure o pastor."

    def test_deny_without_body(self, leader: APIClient, sender: FakePushSender) -> None:
        request = _request(_account("ana", "Ana"))
        response = leader.post(decision_url(request.pk, "deny"))
        assert response.status_code == 200
        assert response.data["requests"][0]["denial_reason"] is None

    def test_deny_reason_too_long(self, leader: APIClient, sender: FakePushSender) -> None:
        request = _request(_account("ana", "Ana"))
        response = leader.post(
            decision_url(request.pk, "deny"), {"reason": "x" * 501}, format="json"
        )
        assert response.status_code == 400

    def test_deciding_twice_is_a_conflict(self, leader: APIClient, sender: FakePushSender) -> None:
        request = _request(_account("ana", "Ana"))
        leader.post(decision_url(request.pk, "approve"))
        response = leader.post(decision_url(request.pk, "deny"))
        assert response.status_code == 409
        assert response.data["error_code"] == "ACCESS_REQUEST_NOT_PENDING"
        assert len(sender.calls) == 0  # nobody had a device

    def test_unknown_request(self, leader: APIClient, sender: FakePushSender) -> None:
        assert leader.post(decision_url(999, "approve")).status_code == 404


class TestAccess:
    @pytest.mark.parametrize(
        ("method", "url"),
        [
            ("get", PROFILES_URL),
            ("get", f"{PROFILES_URL}00000000-0000-0000-0000-000000000001/"),
            ("patch", f"{PROFILES_URL}00000000-0000-0000-0000-000000000001/"),
            ("post", f"{PROFILES_URL}00000000-0000-0000-0000-000000000001/revoke-access/"),
            ("post", decision_url(1, "approve")),
            ("post", decision_url(1, "deny")),
        ],
    )
    @pytest.mark.parametrize("caller", ["media", "member", "anonymous"])
    def test_refused(self, method: str, url: str, caller: str) -> None:
        clients = {
            "media": lambda: make_role_client(Role.MEDIA, username="media")[0],
            "member": lambda: make_member_client()[0],
            "anonymous": lambda: APIClient(),
        }
        response = getattr(clients[caller](), method)(url, {}, format="json")
        assert response.status_code == (401 if caller == "anonymous" else 403)

    def test_admin_may_list(self) -> None:
        client, _ = make_role_client(Role.ADMIN, username="admin")
        assert client.get(PROFILES_URL).status_code == 200

    def test_no_role_refused(self) -> None:
        assert make_auth_client(make_user(username="plain")).get(PROFILES_URL).status_code == 403
