"""Device push token endpoints (specs/017-sunday-setlist-push, contracts/me-api.md)."""

from typing import Any

import pytest
from rest_framework.test import APIClient

from conftest import make_auth_client, make_user
from core.models import DeviceToken

REGISTER = "/api/me/devices/"
UNREGISTER = "/api/me/devices/unregister/"


@pytest.mark.django_db
class TestDeviceTokens:
    def setup_method(self) -> None:
        self.ana = make_user(username="ana")
        self.bia = make_user(username="bia")
        self.ana_client = make_auth_client(self.ana)
        self.bia_client = make_auth_client(self.bia)

    @pytest.mark.parametrize("url", [REGISTER, UNREGISTER])
    def test_anonymous_is_401(self, url: str) -> None:
        assert APIClient().post(url, {"token": "t1"}, format="json").status_code == 401

    def test_register_is_idempotent(self) -> None:
        for _ in range(2):
            response = self.ana_client.post(REGISTER, {"token": "t1"}, format="json")
            assert response.status_code == 204
        assert list(DeviceToken.objects.values_list("token", "user_id")) == [("t1", self.ana.pk)]

    def test_same_phone_new_account_moves_the_token(self) -> None:
        self.ana_client.post(REGISTER, {"token": "t1"}, format="json")
        self.bia_client.post(REGISTER, {"token": "t1"}, format="json")
        assert DeviceToken.objects.get().user_id == self.bia.pk

    def test_unregister_someone_elses_token_changes_nothing(self) -> None:
        self.bia_client.post(REGISTER, {"token": "t1"}, format="json")
        response = self.ana_client.post(UNREGISTER, {"token": "t1"}, format="json")
        assert response.status_code == 204
        assert DeviceToken.objects.filter(token="t1", user=self.bia).exists()

    def test_unregister_own_token(self) -> None:
        self.ana_client.post(REGISTER, {"token": "t1"}, format="json")
        assert self.ana_client.post(UNREGISTER, {"token": "t1"}, format="json").status_code == 204
        assert not DeviceToken.objects.exists()

    def test_unregister_unknown_token_is_204(self) -> None:
        response = self.ana_client.post(UNREGISTER, {"token": "never-seen"}, format="json")
        assert response.status_code == 204

    @pytest.mark.parametrize("body", [[], {"token": ""}, {"token": 5}, {}, {"token": "a b"}])
    def test_malformed_body_is_400(self, body: Any) -> None:
        response = self.ana_client.post(REGISTER, body, format="json")
        assert response.status_code == 400
        assert response.data["error_code"] == "VALIDATION_ERROR"
