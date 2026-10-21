"""US1/US5 — POST api/me/access-requests/ (specs/022-access-requests contracts/access-api.md)."""

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
from features.accounts.tests.integration.access_helpers import (
    ME_REQUESTS_URL,
    PROFILE_URL,
    frozen_at,
    register_device,
    tokens_messaged,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def sender(di_container: Container) -> Iterator[FakePushSender]:
    fake = FakePushSender()
    with di_container.push_sender.override(providers.Object(fake)):
        yield fake


def _visitor(username: str = "visitor") -> APIClient:
    return make_auth_client(make_user(username=username))


def _age_requests(hours: int) -> None:
    AccessRequest.objects.update(created_at=timezone.now() - timedelta(hours=hours))


class TestCreate:
    def test_access_request_is_created(self, sender: FakePushSender) -> None:
        response = _visitor().post(
            ME_REQUESTS_URL, {"type": "access", "message": " Sou membro. "}, format="json"
        )
        assert response.status_code == 201
        assert set(response.data) == {
            "id",
            "type",
            "message",
            "status",
            "created_at",
            "decided_by",
            "decided_at",
            "denial_reason",
        }
        assert response.data["message"] == "Sou membro."
        assert response.data["status"] == "pending"

    def test_profile_shows_pending(self, sender: FakePushSender) -> None:
        client = _visitor()
        client.post(ME_REQUESTS_URL, {"type": "access"}, format="json")
        assert client.get(PROFILE_URL).data["access_status"] == "pending"

    def test_leaders_are_notified_and_nobody_else(self, sender: FakePushSender) -> None:
        _, leader = make_role_client(Role.LEADER, username="leader")
        _, admin = make_role_client(Role.ADMIN, username="admin")
        _, media = make_role_client(Role.MEDIA, username="media")
        requester = make_user(username="requester")
        for user, token in ((leader, "t-leader"), (admin, "t-admin"), (media, "t-media")):
            register_device(user, token)
        register_device(requester, "t-requester")

        created = make_auth_client(requester).post(
            ME_REQUESTS_URL, {"type": "access"}, format="json"
        )

        [(tokens, payload)] = tokens_messaged(sender)
        assert tokens == {"t-leader", "t-admin"}
        assert payload == {
            "type": "access_request_created",
            "request_id": str(created.data["id"]),
            "request_type": "access",
        }


class TestRefusals:
    def test_same_type_pending(self, sender: FakePushSender) -> None:
        client = _visitor()
        client.post(ME_REQUESTS_URL, {"type": "access"}, format="json")
        response = client.post(ME_REQUESTS_URL, {"type": "access"}, format="json")
        assert response.status_code == 409
        assert response.data["error_code"] == "ACCESS_REQUEST_PENDING"
        assert AccessRequest.objects.count() == 1

    def test_flag_holder_already_has_access(self, sender: FakePushSender) -> None:
        client, _ = make_member_client()
        response = client.post(ME_REQUESTS_URL, {"type": "access"}, format="json")
        assert response.status_code == 409
        assert response.data["error_code"] == "MEMBER_ACCESS_ALREADY_GRANTED"

    def test_leader_already_has_access(self, sender: FakePushSender) -> None:
        client, _ = make_role_client(Role.LEADER)
        response = client.post(ME_REQUESTS_URL, {"type": "access"}, format="json")
        assert response.data["error_code"] == "MEMBER_ACCESS_ALREADY_GRANTED"

    def test_blocked(self, sender: FakePushSender) -> None:
        user = make_user(username="blocked")
        user.profile.access_requests_blocked = True
        user.profile.save()
        response = make_auth_client(user).post(ME_REQUESTS_URL, {"type": "access"}, format="json")
        assert response.status_code == 403
        assert response.data["error_code"] == "ACCESS_REQUESTS_BLOCKED"
        assert response.data["detail"] == "Pedidos de acesso indisponíveis. Fale com a liderança."
        assert sender.calls == []

    def test_second_request_within_a_day(
        self, di_container: Container, sender: FakePushSender
    ) -> None:
        client = _visitor()
        client.post(ME_REQUESTS_URL, {"type": "access"}, format="json")
        AccessRequest.objects.update(status="denied")
        _age_requests(hours=23)

        response = client.post(ME_REQUESTS_URL, {"type": "access"}, format="json")

        assert response.status_code == 429
        assert response.data["error_code"] == "ACCESS_REQUEST_RATE_LIMITED"
        assert 3500 < response.data["retry_after_seconds"] <= 3600

    def test_other_type_counts_for_the_day(self, sender: FakePushSender) -> None:
        client = _visitor()
        client.post(ME_REQUESTS_URL, {"type": "access"}, format="json")
        response = client.post(
            ME_REQUESTS_URL, {"type": "data_correction", "message": "x"}, format="json"
        )
        assert response.status_code == 429

    def test_after_a_day_it_is_accepted(
        self, di_container: Container, sender: FakePushSender
    ) -> None:
        client = _visitor()
        client.post(ME_REQUESTS_URL, {"type": "access"}, format="json")
        AccessRequest.objects.update(status="denied")
        _age_requests(hours=25)
        with frozen_at(di_container, timezone.now()):
            response = client.post(ME_REQUESTS_URL, {"type": "access"}, format="json")
        assert response.status_code == 201

    @pytest.mark.parametrize(
        ("body", "field"),
        [
            ({"type": "member"}, "type"),
            ({}, "type"),
            ({"type": "data_correction"}, "message"),
            ({"type": "data_correction", "message": "   "}, "message"),
            ({"type": "access", "message": "x" * 1001}, "message"),
        ],
    )
    def test_validation(self, sender: FakePushSender, body: dict[str, str], field: str) -> None:
        response = _visitor().post(ME_REQUESTS_URL, body, format="json")
        assert response.status_code == 400
        assert field in response.data["field_errors"]
        assert AccessRequest.objects.count() == 0

    def test_body_must_be_an_object(self, sender: FakePushSender) -> None:
        response = _visitor().post(ME_REQUESTS_URL, ["access"], format="json")
        assert response.status_code == 400

    def test_anonymous(self) -> None:
        assert (
            APIClient().post(ME_REQUESTS_URL, {"type": "access"}, format="json").status_code == 401
        )


class TestCorrection:
    def test_member_asks_for_a_correction(self, sender: FakePushSender) -> None:
        client, _ = make_member_client()
        response = client.post(
            ME_REQUESTS_URL,
            {"type": "data_correction", "message": "Meu batismo foi em 2001."},
            format="json",
        )
        assert response.status_code == 201
        assert client.get(PROFILE_URL).data["data_correction_pending"] is True
