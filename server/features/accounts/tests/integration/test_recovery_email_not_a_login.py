"""The security invariant (specs/028-password-recovery US4, constitution): a user-typed e-mail never
identifies an account or links a sign-in. See TODO/alerta-email-vinculo-google.md for the takeover
these tests keep closed."""

from unittest.mock import patch

import pytest
from dependency_injector import providers
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from config.di import Container
from features.accounts.models.user import User
from features.accounts.tests.fakes import FakeAvatarDownloader
from features.accounts.tests.integration.recovery_helpers import make_recovery_user

GOOGLE_URL = "/api/auth/google/"
LOGIN_URL = "/api/auth/login/"
REGISTER_URL = "/api/auth/register/"
DELETE_URL = "/api/me/delete/"
VERIFY_TOKEN = "features.accounts.services.google_auth_service.id_token.verify_oauth2_token"
VICTIM_ADDRESS = "victim@gmail.com"

pytestmark = pytest.mark.django_db


def _google_payload(email: str = VICTIM_ADDRESS) -> dict[str, object]:
    return {"email": email, "email_verified": True, "given_name": "Victim", "family_name": "V"}


def _google_sign_in(di_container: Container) -> dict[str, str]:
    with (
        di_container.avatar_downloader.override(providers.Object(FakeAvatarDownloader())),
        patch(VERIFY_TOKEN, return_value=_google_payload()),
    ):
        response = APIClient().post(GOOGLE_URL, {"id_token": "fake"}, format="json")
    assert response.status_code == 200
    return dict(response.data)


def _signed_in_id(tokens: dict[str, str]) -> str:
    return str(AccessToken(tokens["access"])["user_id"])  # type: ignore[arg-type]


def test_google_sign_in_does_not_enter_the_account_holding_that_recovery_email(
    di_container: Container,
) -> None:
    attacker = make_recovery_user("attacker", VICTIM_ADDRESS)

    tokens = _google_sign_in(di_container)

    signed_in = _signed_in_id(tokens)
    assert str(signed_in) != str(attacker.pk)
    assert User.objects.get(pk=signed_in).email == VICTIM_ADDRESS


def test_attack_by_registration_does_not_reach_the_google_account(
    di_container: Container,
) -> None:
    """The whole attack: register with the victim's address, wait for the victim's Google sign-in."""
    body = {
        "username": "attacker",
        "first_name": "A",
        "last_name": "B",
        "password": "secret1",
        "password_confirm": "secret1",
        "recovery_email": VICTIM_ADDRESS,
    }
    assert APIClient().post(REGISTER_URL, body, format="json").status_code == 201
    assert User.objects.get(username="attacker").email == ""

    tokens = _google_sign_in(di_container)

    signed_in = User.objects.get(pk=_signed_in_id(tokens))
    assert signed_in.username != "attacker"


def test_google_confirmation_of_deletion_does_not_resolve_a_recovery_email(
    di_container: Container,
) -> None:
    """``resolve_existing_account`` uses the same lookup, and deleting by it would be worse."""
    service = di_container.google_auth_service()
    make_recovery_user("attacker", VICTIM_ADDRESS)

    with patch(VERIFY_TOKEN, return_value=_google_payload()):
        assert service.resolve_existing_account("fake") is None


@pytest.mark.parametrize("typed", [VICTIM_ADDRESS, VICTIM_ADDRESS.upper()])
def test_recovery_email_is_not_a_login(typed: str) -> None:
    make_recovery_user("ana", VICTIM_ADDRESS)

    body = {"username": typed, "password": "secret1"}
    assert APIClient().post(LOGIN_URL, body, format="json").status_code == 401
