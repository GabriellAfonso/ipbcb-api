"""The public recovery flow end to end (specs/028-password-recovery US1)."""

from collections.abc import Callable, Iterator
from datetime import timedelta
from typing import Any

import pytest
from axes.models import AccessAttempt
from dependency_injector import providers
from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from config.di import Container
from features.accounts.domain.email_codes import address_key
from features.accounts.models.email_code import EmailCode, EmailSendLedger
from features.accounts.models.user import User
from features.accounts.repositories.email_sender import SmtpEmailSender
from features.accounts.tests.integration.recovery_helpers import (
    code_for,
    make_recovery_user,
    wrong_code,
)

REQUEST_URL = "/api/auth/password-recovery/request/"
CONFIRM_URL = "/api/auth/password-recovery/confirm/"
LOGIN_URL = "/api/auth/login/"
REFRESH_URL = "/api/auth/refresh/"
ADDRESS = "ana@example.com"
NEW_PASSWORD = "nova-senha"  # nosec B105

pytestmark = pytest.mark.django_db

CaptureOnCommit = Callable[..., Any]


@pytest.fixture(autouse=True)
def deliver_synchronously(di_container: Container) -> Iterator[None]:
    """Delivery without the thread, so the outbox is ready when the request returns."""
    with di_container.email_sender.override(providers.Object(SmtpEmailSender())):
        yield


@pytest.fixture(autouse=True)
def clear_attempts() -> Iterator[None]:
    yield
    AccessAttempt.objects.all().delete()


@pytest.fixture
def ask(django_capture_on_commit_callbacks: CaptureOnCommit) -> Callable[..., Response]:
    def _ask(address: str = ADDRESS) -> Response:
        with django_capture_on_commit_callbacks(execute=True):
            return APIClient().post(REQUEST_URL, {"email": address}, format="json")

    return _ask


def _confirm(code: str, address: str = ADDRESS, password: str = NEW_PASSWORD) -> Response:
    body = {
        "email": address,
        "code": code,
        "new_password": password,
        "new_password_confirm": password,
    }
    return APIClient().post(CONFIRM_URL, body, format="json")


def _login(username: str, password: str) -> Response:
    body = {"username": username, "password": password}
    return APIClient().post(LOGIN_URL, body, format="json")


def _forget_send_limit() -> None:
    EmailSendLedger.objects.all().delete()


# ─── Request ────────────────────────────────────────────────────────────────────────────────


def test_request_sends_username_and_code(ask: Callable[..., Response]) -> None:
    make_recovery_user()

    response = ask()

    assert response.status_code == 200
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [ADDRESS]
    assert code_for("ana")


def test_answer_is_identical_with_and_without_an_account(ask: Callable[..., Response]) -> None:
    make_recovery_user()

    with_account = ask()
    without_account = ask("nobody@example.com")

    assert with_account.status_code == without_account.status_code
    assert with_account.data == without_account.data
    assert len(mail.outbox) == 1


def test_address_is_normalised_on_request(ask: Callable[..., Response]) -> None:
    make_recovery_user()

    ask("  ANA@Example.com ")

    assert mail.outbox[0].to == [ADDRESS]


def test_a_malformed_address_is_a_form_error(ask: Callable[..., Response]) -> None:
    response = ask("not-an-email")

    assert response.status_code == 400
    assert response.data["field_errors"]["email"] == ["Informe um e-mail válido."]


def test_body_that_is_not_an_object_is_a_400() -> None:
    assert APIClient().post(REQUEST_URL, ["a"], format="json").status_code == 400
    assert APIClient().post(CONFIRM_URL, ["a"], format="json").status_code == 400


def test_an_expired_token_does_not_break_the_public_flow(ask: Callable[..., Response]) -> None:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Bearer expired-or-garbage")

    assert client.post(REQUEST_URL, {"email": ADDRESS}, format="json").status_code == 200


def test_accounts_sharing_an_address_get_one_message_with_different_codes(
    ask: Callable[..., Response],
) -> None:
    make_recovery_user("ana")
    make_recovery_user("joao")

    ask()

    assert len(mail.outbox) == 1
    assert code_for("ana") != code_for("joao")


def test_unconfirmed_address_can_recover(ask: Callable[..., Response]) -> None:
    user = make_recovery_user()
    assert user.profile.recovery_email_confirmed_at is None

    ask()

    assert len(mail.outbox) == 1


def test_a_google_only_account_gets_no_code(ask: Callable[..., Response]) -> None:
    user = make_recovery_user()
    user.set_unusable_password()
    user.save()

    assert ask().status_code == 200
    assert mail.outbox == []
    assert not EmailCode.objects.exists()


def test_a_deactivated_account_gets_no_code(ask: Callable[..., Response]) -> None:
    user = make_recovery_user()
    user.is_active = False
    user.save()

    assert ask().status_code == 200
    assert mail.outbox == []


def test_shared_address_skips_only_the_ineligible_account(ask: Callable[..., Response]) -> None:
    make_recovery_user("ana")
    other = make_recovery_user("joao")
    other.is_active = False
    other.save()

    ask()

    assert code_for("ana")
    assert "joao" not in mail.outbox[0].body


def test_codes_are_stored_only_as_a_hash(ask: Callable[..., Response]) -> None:
    make_recovery_user()

    ask()

    assert code_for("ana") not in EmailCode.objects.get().code_digest


def test_an_address_with_no_account_is_not_stored_readable(ask: Callable[..., Response]) -> None:
    ask("nobody@example.com")

    assert "nobody" not in EmailSendLedger.objects.get().address_key


# ─── Limits ─────────────────────────────────────────────────────────────────────────────────


def test_second_request_inside_the_minute_answers_the_same_and_sends_nothing(
    ask: Callable[..., Response],
) -> None:
    make_recovery_user()

    first = ask()
    second = ask()

    assert second.status_code == 200
    assert second.data == first.data
    assert len(mail.outbox) == 1


def test_a_limited_request_keeps_the_code_already_sent(ask: Callable[..., Response]) -> None:
    make_recovery_user()
    ask()
    code = code_for("ana")

    ask()

    assert _confirm(code).status_code == 204


def test_sixth_request_in_the_hour_sends_nothing(ask: Callable[..., Response]) -> None:
    make_recovery_user()
    moments = [timezone.now() - timedelta(minutes=minutes) for minutes in (50, 40, 30, 20, 10)]
    EmailSendLedger.objects.create(
        address_key=address_key(ADDRESS),
        send_times=[moment.isoformat() for moment in moments],
    )

    assert ask().status_code == 200
    assert mail.outbox == []


def test_client_over_its_limit_gets_the_same_answer_and_nothing_is_sent(
    ask: Callable[..., Response], monkeypatch: pytest.MonkeyPatch
) -> None:
    make_recovery_user()
    monkeypatch.setattr(
        ScopedRateThrottle, "THROTTLE_RATES", {"recovery_request": "1/hour", "login": "99/min"}
    )
    cache.clear()
    first = ask("someone@example.com")

    second = ask()
    cache.clear()

    assert second.status_code == 200
    assert second.data == first.data
    assert mail.outbox == []


# ─── Confirm ────────────────────────────────────────────────────────────────────────────────


def test_confirm_sets_the_password_and_returns_no_tokens(ask: Callable[..., Response]) -> None:
    make_recovery_user()
    ask()

    response = _confirm(code_for("ana"))

    assert response.status_code == 204
    assert not response.data
    assert _login("ana", NEW_PASSWORD).status_code == 200
    assert _login("ana", "secret1").status_code == 401


def test_confirm_revokes_old_sessions(ask: Callable[..., Response]) -> None:
    make_recovery_user()
    old = _login("ana", "secret1").data
    ask()

    _confirm(code_for("ana"))

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {old['access']}")
    assert client.get("/api/me/profile/").status_code == 401
    assert (
        APIClient().post(REFRESH_URL, {"refresh": old["refresh"]}, format="json").status_code == 401
    )


def test_a_used_code_gives_the_generic_error(ask: Callable[..., Response]) -> None:
    make_recovery_user()
    ask()
    code = code_for("ana")
    _confirm(code)

    response = _confirm(code, password="outra-senha")

    assert response.status_code == 400
    assert response.data["error_code"] == "INVALID_EMAIL_CODE"
    assert _login("ana", NEW_PASSWORD).status_code == 200


def test_wrong_expired_and_used_give_the_same_error(ask: Callable[..., Response]) -> None:
    make_recovery_user()
    ask()
    code = code_for("ana")
    wrong = _confirm(wrong_code(code))
    EmailCode.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
    expired = _confirm(code)
    EmailCode.objects.all().delete()
    used = _confirm(code)

    assert wrong.status_code == expired.status_code == used.status_code == 400
    assert wrong.data == expired.data == used.data
    assert wrong.data["detail"] == "Código inválido ou expirado."


def test_an_unknown_address_gets_the_same_error(ask: Callable[..., Response]) -> None:
    make_recovery_user()
    ask()
    known = _confirm(wrong_code(code_for("ana")))

    unknown = _confirm("123456", address="nobody@example.com")

    assert unknown.status_code == known.status_code
    assert unknown.data == known.data


def test_a_code_of_one_address_does_not_work_for_another(ask: Callable[..., Response]) -> None:
    make_recovery_user("ana")
    make_recovery_user("joao", "joao@example.com")
    ask()

    assert _confirm(code_for("ana"), address="joao@example.com").status_code == 400
    assert _login("joao", NEW_PASSWORD).status_code == 401


def test_the_code_decides_which_account_changes(ask: Callable[..., Response]) -> None:
    make_recovery_user("ana")
    make_recovery_user("joao")
    ask()

    assert _confirm(code_for("joao")).status_code == 204

    assert _login("joao", NEW_PASSWORD).status_code == 200
    assert _login("ana", "secret1").status_code == 200


def test_recovering_one_account_leaves_the_other_code_working(
    ask: Callable[..., Response],
) -> None:
    make_recovery_user("ana")
    make_recovery_user("joao")
    ask()
    ana, joao = code_for("ana"), code_for("joao")

    _confirm(ana)

    assert _confirm(joao).status_code == 204


@pytest.mark.parametrize(
    ("password", "confirm", "field", "message"),
    [
        ("abc", "abc", "new_password", "A senha precisa ter ao menos 6 caracteres."),
        ("nova-senha", "outra-senha", "new_password_confirm", "As senhas não coincidem."),
    ],
)
def test_new_password_errors_keep_the_code(
    ask: Callable[..., Response], password: str, confirm: str, field: str, message: str
) -> None:
    make_recovery_user()
    ask()
    code = code_for("ana")
    body = {
        "email": ADDRESS,
        "code": code,
        "new_password": password,
        "new_password_confirm": confirm,
    }

    response = APIClient().post(CONFIRM_URL, body, format="json")

    assert response.status_code == 400
    assert response.data["field_errors"][field] == [message]
    assert EmailCode.objects.get().failed_attempts == 0
    assert _confirm(code).status_code == 204


@pytest.mark.parametrize("change", ["deactivate", "unusable_password", "other_address"])
def test_an_account_that_stopped_matching_cannot_use_its_code(
    ask: Callable[..., Response], change: str
) -> None:
    user = make_recovery_user()
    ask()
    code = code_for("ana")
    if change == "deactivate":
        user.is_active = False
    elif change == "unusable_password":
        user.set_unusable_password()
    else:
        user.profile.recovery_email = "other@example.com"
        user.profile.save()
    user.save()

    assert _confirm(code).status_code == 400


# ─── Attempts ───────────────────────────────────────────────────────────────────────────────


def test_five_wrong_attempts_kill_the_correct_code(ask: Callable[..., Response]) -> None:
    make_recovery_user()
    ask()
    code = code_for("ana")

    for _ in range(5):
        assert _confirm(wrong_code(code)).status_code == 400

    assert _confirm(code).status_code == 400
    assert _login("ana", "secret1").status_code == 200


def test_the_correct_code_still_works_after_four_wrong_attempts(
    ask: Callable[..., Response],
) -> None:
    make_recovery_user()
    ask()
    code = code_for("ana")

    for _ in range(4):
        _confirm(wrong_code(code))

    assert _confirm(code).status_code == 204


def test_wrong_attempts_count_per_address_not_per_account(ask: Callable[..., Response]) -> None:
    """Regression guard for the core of FR-017: three accounts must not give 15 guesses."""
    for username in ("ana", "joao", "maria"):
        make_recovery_user(username)
    ask()
    codes = [code_for(username) for username in ("ana", "joao", "maria")]

    for _ in range(5):
        _confirm(wrong_code(*codes))

    assert not EmailCode.objects.exists()
    assert all(_confirm(code).status_code == 400 for code in codes)


def test_a_new_request_replaces_the_old_code_and_restarts_the_count(
    ask: Callable[..., Response],
) -> None:
    make_recovery_user()
    ask()
    old = code_for("ana")
    _confirm(wrong_code(old))
    _forget_send_limit()

    ask()
    new = code_for("ana")

    assert EmailCode.objects.get().failed_attempts == 0
    if old != new:
        assert _confirm(old).status_code == 400
    assert _confirm(new).status_code == 204


# ─── Lockout ────────────────────────────────────────────────────────────────────────────────


@override_settings(AXES_ENABLED=True)
def test_recovery_clears_the_login_lockout(ask: Callable[..., Response]) -> None:
    make_recovery_user()
    for _ in range(5):
        _login("ana", "wrong-password")
    assert _login("ana", NEW_PASSWORD).status_code == 429
    ask()

    assert _confirm(code_for("ana")).status_code == 204

    assert _login("ana", NEW_PASSWORD).status_code == 200


@override_settings(AXES_ENABLED=True)
def test_a_failed_recovery_keeps_the_lockout(ask: Callable[..., Response]) -> None:
    make_recovery_user()
    for _ in range(5):
        _login("ana", "wrong-password")
    ask()

    _confirm(wrong_code(code_for("ana")))

    assert _login("ana", "secret1").status_code == 429


def test_account_deletion_removes_its_codes(ask: Callable[..., Response]) -> None:
    make_recovery_user()
    ask()

    User.objects.get(username="ana").delete()

    assert not EmailCode.objects.exists()
