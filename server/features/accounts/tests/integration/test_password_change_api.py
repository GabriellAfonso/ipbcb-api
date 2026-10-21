"""POST api/me/password/ end to end (specs/021-user-account US3, contracts/account-api.md)."""

import json

from collections.abc import Iterator

import pytest
from axes.models import AccessAttempt
from django.test import override_settings
from rest_framework.response import Response
from rest_framework.test import APIClient

from conftest import make_auth_client, make_user
from features.accounts.models.user import User

PASSWORD_URL = "/api/me/password/"
LOGIN_URL = "/api/auth/login/"
REFRESH_URL = "/api/auth/refresh/"
PROFILE_URL = "/api/me/profile/"

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_attempts() -> Iterator[None]:
    yield
    AccessAttempt.objects.all().delete()


def _session(username: str = "ana", password: str = "secret1") -> tuple[APIClient, str]:
    """Sign in like the app does; return (client with the access token, refresh token)."""
    pair = APIClient().post(LOGIN_URL, {"username": username, "password": password}, format="json")
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {pair.data['access']}")
    return client, pair.data["refresh"]


def _change(client: APIClient, current: str, new: str, confirm: str | None = None) -> Response:
    body = {"current_password": current, "new_password": new}
    body["new_password_confirm"] = new if confirm is None else confirm
    response: Response = client.post(PASSWORD_URL, body, format="json")
    return response


def _refresh(token: str) -> int:
    return APIClient().post(REFRESH_URL, {"refresh": token}, format="json").status_code


def test_change_keeps_the_caller_and_signs_out_everyone_else() -> None:
    make_user(username="ana", password="secret1")
    device_a, refresh_a = _session()
    device_b, refresh_b = _session()

    response = _change(device_a, "secret1", "new-secret")

    assert response.status_code == 200
    assert set(response.data) == {"access", "refresh"}
    # Every old token is dead, the caller's included.
    assert device_a.get(PROFILE_URL).status_code == 401
    assert device_b.get(PROFILE_URL).status_code == 401
    assert _refresh(refresh_a) == 401
    assert _refresh(refresh_b) == 401
    # The pair in the response works.
    fresh = APIClient()
    fresh.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    assert fresh.get(PROFILE_URL).status_code == 200
    assert _refresh(response.data["refresh"]) == 200
    assert User.objects.get(username="ana").check_password("new-secret")


def test_wrong_current_password_is_400_and_keeps_the_session() -> None:
    make_user(username="ana", password="secret1")
    client, _ = _session()
    response = _change(client, "wrong!", "new-secret")
    assert response.status_code == 400
    assert response.data["error_code"] == "INVALID_PASSWORD"
    assert client.get(PROFILE_URL).status_code == 200


@pytest.mark.parametrize(
    ("new", "confirm", "field", "message"),
    [
        ("12345", "12345", "new_password", "A senha precisa ter ao menos 6 caracteres."),
        ("new-secret", "other-secret", "new_password_confirm", "As senhas não coincidem."),
    ],
)
def test_registration_rules_apply(new: str, confirm: str, field: str, message: str) -> None:
    make_user(username="ana", password="secret1")
    client, _ = _session()
    response = _change(client, "secret1", new, confirm)
    assert response.status_code == 400
    assert response.data["field_errors"][field] == [message]


def test_missing_current_password_is_a_field_error() -> None:
    make_user(username="ana", password="secret1")
    client, _ = _session()
    response = client.post(
        PASSWORD_URL, {"new_password": "abcdef", "new_password_confirm": "abcdef"}, format="json"
    )
    assert response.data["field_errors"]["current_password"] == ["Este campo é obrigatório."]


def test_new_password_may_equal_the_old_one() -> None:
    make_user(username="ana", password="secret1")
    client, _ = _session()
    assert _change(client, "secret1", "secret1").status_code == 200


def test_google_only_account_gets_409() -> None:
    user = make_user(username="gabi")
    user.set_unusable_password()
    user.save(update_fields=["password"])
    response = _change(make_auth_client(user), "anything", "new-secret")
    assert response.status_code == 409
    assert response.data["error_code"] == "PASSWORD_NOT_SET"


@override_settings(AXES_ENABLED=True)
def test_lockout_after_five_wrong_passwords() -> None:
    make_user(username="ana", password="secret1")
    client, _ = _session()
    for _ in range(5):
        _change(client, "wrong!", "new-secret")
    response = _change(client, "secret1", "new-secret")
    assert response.status_code == 429
    assert json.loads(response.content)["error_code"] == "ACCOUNT_LOCKED"
    assert User.objects.get(username="ana").check_password("secret1")


def test_requires_authentication() -> None:
    assert _change(APIClient(), "secret1", "new-secret").status_code == 401
