"""The account-deletion web page, CSRF enforced (specs/021-user-account US2)."""

from collections.abc import Iterator
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from axes.models import AccessAttempt
from django.core.cache import cache
from django.test import Client, override_settings

from conftest import make_user
from features.accounts.models.user import User
from features.accounts.views.account_deletion_page import AccountDeletionPageThrottle

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse

PAGE_URL = "/conta/excluir/"
VERIFY_PATH = "features.accounts.services.google_auth_service.id_token.verify_oauth2_token"
GOOGLE_CLIENT_ID = "1234-web.apps.googleusercontent.com"

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clean_state() -> Iterator[None]:
    yield
    AccessAttempt.objects.all().delete()
    cache.clear()  # throttle history


def _browser() -> tuple[Client, str]:
    """A client that enforces CSRF like a browser, and the token its first GET received."""
    client = Client(enforce_csrf_checks=True)
    client.get(PAGE_URL)
    return client, client.cookies["csrftoken"].value


def _post_password(
    username: str, password: str, confirm: bool = True
) -> "_MonkeyPatchedWSGIResponse":
    client, token = _browser()
    body = {"csrfmiddlewaretoken": token, "method": "password", "username": username}
    body["password"] = password
    if confirm:
        body["confirm"] = "on"
    return client.post(PAGE_URL, body)


def _post_google(credential: str = "google-token") -> "_MonkeyPatchedWSGIResponse":
    client, token = _browser()
    body = {"csrfmiddlewaretoken": token, "method": "google", "credential": credential}
    return client.post(PAGE_URL, {**body, "confirm": "on"})


def _google_only(email: str = "gabi@gmail.com") -> User:
    user = make_user(username="gabi", email=email)
    user.set_unusable_password()
    user.save()
    return user


def _google_payload(email: str) -> dict[str, object]:
    return {"email": email, "email_verified": True}


class TestGet:
    def test_explains_and_offers_the_form(self) -> None:
        response = Client().get(PAGE_URL)
        html = response.content.decode()
        assert response.status_code == 200
        assert "O que é apagado" in html
        assert "O que é mantido" in html
        assert 'name="csrfmiddlewaretoken"' in html
        assert "no-store" in response["Cache-Control"] or "max-age=0" in response["Cache-Control"]

    def test_headers_let_the_google_button_work(self) -> None:
        response = Client().get(PAGE_URL)
        assert response["Cross-Origin-Opener-Policy"] == "same-origin-allow-popups"
        assert response["Referrer-Policy"] == "strict-origin-when-cross-origin"

    @override_settings(GOOGLE_CLIENT_ID=GOOGLE_CLIENT_ID)
    def test_google_button_when_client_id_is_set(self) -> None:
        html = Client().get(PAGE_URL).content.decode()
        assert f'data-client_id="{GOOGLE_CLIENT_ID}"' in html
        assert "accounts.google.com/gsi/client" in html

    @override_settings(GOOGLE_CLIENT_ID="")
    def test_no_google_button_without_client_id(self) -> None:
        assert "gsi/client" not in Client().get(PAGE_URL).content.decode()


class TestPasswordForm:
    def test_right_credentials_delete_the_account(self) -> None:
        make_user(username="ana", password="secret1")
        response = _post_password(" ANA ", "secret1")
        assert response.status_code == 200
        assert "Sua conta foi excluída" in response.content.decode()
        assert not User.objects.filter(username="ana").exists()

    @pytest.mark.parametrize(("username", "password"), [("ana", "wrong!"), ("nobody", "secret1")])
    def test_failure_is_generic(self, username: str, password: str) -> None:
        make_user(username="ana", password="secret1")
        response = _post_password(username, password)
        assert "Usuário ou senha inválidos." in response.content.decode()
        assert User.objects.filter(username="ana").exists()

    def test_unticked_confirmation_deletes_nothing(self) -> None:
        make_user(username="ana", password="secret1")
        response = _post_password("ana", "secret1", confirm=False)
        assert "Marque a caixa" in response.content.decode()
        assert User.objects.filter(username="ana").exists()

    def test_superuser_is_blocked(self) -> None:
        user = make_user(username="root", password="secret1")
        user.is_superuser = True
        user.save()
        response = _post_password("root", "secret1")
        assert "Fale com a liderança" in response.content.decode()
        assert User.objects.filter(username="root").exists()

    def test_post_without_csrf_token_is_refused(self) -> None:
        make_user(username="ana", password="secret1")
        client = Client(enforce_csrf_checks=True)
        body = {"method": "password", "username": "ana", "password": "secret1", "confirm": "on"}
        response = client.post(PAGE_URL, body)
        assert response.status_code == 403
        assert User.objects.filter(username="ana").exists()

    @override_settings(AXES_ENABLED=True)
    def test_lockout_renders_html_429(self) -> None:
        make_user(username="ana", password="secret1")
        for _ in range(5):
            _post_password("ana", "wrong!")
        response = _post_password("ana", "secret1")
        assert response.status_code == 429
        assert response["Content-Type"].startswith("text/html")
        assert "Tente novamente em 30 minutos" in response.content.decode()
        assert User.objects.filter(username="ana").exists()


class TestGoogleForm:
    def test_google_only_account_is_deleted(self) -> None:
        user = _google_only()
        with patch(VERIFY_PATH, return_value=_google_payload("gabi@gmail.com")):
            response = _post_google()
        assert "Sua conta foi excluída" in response.content.decode()
        assert not User.objects.filter(pk=user.pk).exists()

    def test_account_with_password_must_sign_in_with_it(self) -> None:
        make_user(username="ana", password="secret1", email="ana@gmail.com")
        with patch(VERIFY_PATH, return_value=_google_payload("ana@gmail.com")):
            response = _post_google()
        assert "Esta conta tem senha; entre com usuário e senha." in response.content.decode()
        assert User.objects.filter(username="ana").exists()

    def test_no_account_for_this_google_account(self) -> None:
        with patch(VERIFY_PATH, return_value=_google_payload("stranger@gmail.com")):
            response = _post_google()
        assert "Nenhuma conta do app usa esta conta Google." in response.content.decode()

    def test_invalid_token(self) -> None:
        with patch(VERIFY_PATH, side_effect=ValueError("expired")):
            response = _post_google()
        assert "Não foi possível confirmar com o Google" in response.content.decode()

    def test_missing_credential(self) -> None:
        response = _post_google(credential="")
        assert "Entre com o Google antes de confirmar." in response.content.decode()


def test_throttle_answers_429() -> None:
    # THROTTLE_RATES is read from the settings when DRF is imported; lower it for this test.
    with patch.object(AccountDeletionPageThrottle, "THROTTLE_RATES", {"login": "2/min"}):
        statuses = [_post_password("nobody", "secret1").status_code for _ in range(3)]
    assert statuses == [200, 200, 429]
