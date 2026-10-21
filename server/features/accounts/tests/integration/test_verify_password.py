"""LoginService.verify_password / authenticate_credentials under django-axes
(specs/021-user-account FR-012, research R-01)."""

from collections.abc import Iterator

import pytest
from axes.models import AccessAttempt
from django.http import HttpRequest
from django.test import RequestFactory, override_settings

from conftest import make_user
from core.application.dtos.auth_dtos import LoginDTO
from core.domain.exceptions import InvalidCredentialsError, InvalidPasswordError
from features.accounts.services.login_service import LoginService

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_attempts() -> Iterator[None]:
    yield
    AccessAttempt.objects.all().delete()


def _request(address: str = "198.51.100.10") -> HttpRequest:
    return RequestFactory().post("/api/me/password/", REMOTE_ADDR=address)


def test_right_password_passes() -> None:
    user = make_user(username="ana", password="secret1")
    LoginService().verify_password(user, "secret1", _request())


def test_wrong_password_raises_invalid_password() -> None:
    user = make_user(username="ana", password="secret1")
    with pytest.raises(InvalidPasswordError):
        LoginService().verify_password(user, "wrong!", _request())


def test_google_only_account_never_matches() -> None:
    user = make_user(username="ana", password="secret1")
    user.set_unusable_password()
    user.save()
    with pytest.raises(InvalidPasswordError):
        LoginService().verify_password(user, "secret1", _request())


def test_authenticate_credentials_returns_the_account() -> None:
    user = make_user(username="ana", password="secret1")
    found = LoginService().authenticate_credentials(
        LoginDTO(username=" ANA ", password="secret1"), _request()
    )
    assert found.pk == user.pk


def test_authenticate_credentials_unknown_username() -> None:
    with pytest.raises(InvalidCredentialsError):
        LoginService().authenticate_credentials(
            LoginDTO(username="nobody", password="secret1"), _request()
        )


@override_settings(AXES_ENABLED=True)
def test_failures_count_against_the_login_lockout() -> None:
    user = make_user(username="ana", password="secret1")
    request = _request()
    for _ in range(5):
        with pytest.raises(InvalidPasswordError):
            LoginService().verify_password(user, "wrong!", _request())

    # Locked now: even the right password is refused, and the request is flagged for the
    # middleware that answers 429.
    with pytest.raises(InvalidPasswordError):
        LoginService().verify_password(user, "secret1", request)
    assert getattr(request, "axes_locked_out", False) is True
