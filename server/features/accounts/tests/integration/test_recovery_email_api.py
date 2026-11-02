"""The signed-in recovery e-mail end to end (specs/028-password-recovery US3)."""

from collections.abc import Callable, Iterator
from datetime import timedelta
from typing import Any

import pytest
from axes.models import AccessAttempt
from dependency_injector import providers
from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.test import APIClient

from conftest import make_auth_client, make_user
from config.di import Container
from features.accounts.models.email_code import EmailCode, EmailSendLedger
from features.accounts.models.user import User
from features.accounts.repositories.email_sender import SmtpEmailSender
from features.accounts.tests.integration.recovery_helpers import (
    code_for,
    make_recovery_user,
    only_code,
    wrong_code,
)

SET_URL = "/api/me/recovery-email/"
SEND_URL = "/api/me/recovery-email/send-code/"
CONFIRM_URL = "/api/me/recovery-email/confirm/"
PROFILE_URL = "/api/me/profile/"
RECOVERY_REQUEST_URL = "/api/auth/password-recovery/request/"
RECOVERY_CONFIRM_URL = "/api/auth/password-recovery/confirm/"
ADDRESS = "ana@example.com"
NEW_ADDRESS = "novo@example.com"

pytestmark = pytest.mark.django_db

CaptureOnCommit = Callable[..., Any]


@pytest.fixture(autouse=True)
def deliver_synchronously(di_container: Container) -> Iterator[None]:
    with di_container.email_sender.override(providers.Object(SmtpEmailSender())):
        yield


@pytest.fixture(autouse=True)
def clear_attempts() -> Iterator[None]:
    yield
    AccessAttempt.objects.all().delete()


@pytest.fixture
def send_code(
    django_capture_on_commit_callbacks: CaptureOnCommit,
) -> Callable[[APIClient], Response]:
    def _send(client: APIClient) -> Response:
        with django_capture_on_commit_callbacks(execute=True):
            return client.post(SEND_URL)

    return _send


def _set(client: APIClient, address: str = NEW_ADDRESS, password: str = "secret1") -> Response:  # nosec B107
    body = {"recovery_email": address, "current_password": password}
    return client.post(SET_URL, body, format="json")


def _confirm(client: APIClient, code: str) -> Response:
    return client.post(CONFIRM_URL, {"code": code}, format="json")


def _google_only_client() -> APIClient:
    user = make_user(username="googleonly")
    user.set_unusable_password()
    user.save()
    return make_auth_client(user)


# ─── Profile ────────────────────────────────────────────────────────────────────────────────


def test_profile_shows_the_address_and_its_state() -> None:
    client = make_auth_client(make_recovery_user())

    response = client.get(PROFILE_URL)

    assert response.data["recovery_email"] == ADDRESS
    assert response.data["recovery_email_confirmed"] is False


def test_profile_shows_null_with_no_address() -> None:
    response = make_auth_client(make_user(username="old")).get(PROFILE_URL)

    assert response.data["recovery_email"] is None
    assert response.data["recovery_email_confirmed"] is False


def test_profile_patch_cannot_write_the_address() -> None:
    """Otherwise a stolen session could skip the password and take the account by recovery."""
    user = make_recovery_user()

    response = make_auth_client(user).patch(
        PROFILE_URL,
        {"recovery_email": "attacker@example.com", "recovery_email_confirmed": True},
        format="json",
    )

    assert response.status_code == 200
    user.profile.refresh_from_db()
    assert user.profile.recovery_email == ADDRESS
    assert user.profile.recovery_email_confirmed_at is None


# ─── Set or change ──────────────────────────────────────────────────────────────────────────


def test_change_stores_the_normalised_address() -> None:
    user = make_recovery_user()

    response = _set(make_auth_client(user), "  NOVO@Example.COM ")

    assert response.status_code == 200
    assert response.data == {"recovery_email": NEW_ADDRESS, "recovery_email_confirmed": False}
    user.profile.refresh_from_db()
    assert user.profile.recovery_email == NEW_ADDRESS


def test_first_address_on_an_existing_account_also_needs_the_password() -> None:
    user = make_user(username="old", password="secret1")  # nosec B106
    client = make_auth_client(user)

    assert _set(client, password="wrong-password").status_code == 400
    user.profile.refresh_from_db()
    assert user.profile.recovery_email == ""
    assert _set(client).status_code == 200


def test_wrong_password_is_a_form_error_and_does_not_sign_out() -> None:
    user = make_recovery_user()
    client = make_auth_client(user)

    response = _set(client, password="wrong-password")

    assert response.status_code == 400
    assert response.data["error_code"] == "INVALID_PASSWORD"
    assert response.data["detail"] == "Senha incorreta."
    assert client.get(PROFILE_URL).status_code == 200
    user.profile.refresh_from_db()
    assert user.profile.recovery_email == ADDRESS


@override_settings(AXES_ENABLED=True)
def test_wrong_passwords_count_toward_the_lockout() -> None:
    client = make_auth_client(make_recovery_user())

    for _ in range(4):
        assert _set(client, password="wrong-password").status_code == 400

    assert _set(client, password="wrong-password").status_code == 429
    assert _set(client).status_code == 429


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"current_password": "secret1"}, "recovery_email"),
        ({"recovery_email": "not-an-email", "current_password": "secret1"}, "recovery_email"),
        ({"recovery_email": NEW_ADDRESS}, "current_password"),
    ],
)
def test_invalid_input_is_a_form_error(body: dict[str, str], field: str) -> None:
    response = make_auth_client(make_recovery_user()).post(SET_URL, body, format="json")

    assert response.status_code == 400
    assert field in response.data["field_errors"]


def test_changing_clears_the_confirmation(send_code: Callable[[APIClient], Response]) -> None:
    client = make_auth_client(make_recovery_user())
    send_code(client)
    _confirm(client, only_code())

    response = _set(client)

    assert response.data["recovery_email_confirmed"] is False


def test_changing_invalidates_a_pending_confirmation_code(
    send_code: Callable[[APIClient], Response],
) -> None:
    client = make_auth_client(make_recovery_user())
    send_code(client)
    code = only_code()

    _set(client)

    assert _confirm(client, code).status_code == 400


def test_changing_invalidates_a_pending_recovery_code(
    django_capture_on_commit_callbacks: CaptureOnCommit,
) -> None:
    """A code sent to the old address must not open the account after the owner replaced it."""
    client = make_auth_client(make_recovery_user())
    with django_capture_on_commit_callbacks(execute=True):
        APIClient().post(RECOVERY_REQUEST_URL, {"email": ADDRESS}, format="json")
    code = code_for("ana")

    _set(client)

    body = {
        "email": ADDRESS,
        "code": code,
        "new_password": "nova-senha",
        "new_password_confirm": "nova-senha",
    }
    assert APIClient().post(RECOVERY_CONFIRM_URL, body, format="json").status_code == 400


def test_changing_keeps_the_session() -> None:
    client = make_auth_client(make_recovery_user())

    _set(client)

    assert client.get(PROFILE_URL).status_code == 200


def test_the_same_address_is_not_a_change(send_code: Callable[[APIClient], Response]) -> None:
    client = make_auth_client(make_recovery_user())
    send_code(client)
    _confirm(client, only_code())

    response = _set(client, ADDRESS)

    assert response.data == {"recovery_email": ADDRESS, "recovery_email_confirmed": True}


def test_address_is_not_unique() -> None:
    make_recovery_user("joao", NEW_ADDRESS)

    assert _set(make_auth_client(make_recovery_user())).status_code == 200


def test_user_email_is_never_written() -> None:
    """The security invariant, from the writing side."""
    user = make_recovery_user()

    _set(make_auth_client(user))

    assert User.objects.get(pk=user.pk).email == ""


# ─── Send code ──────────────────────────────────────────────────────────────────────────────


def test_send_code_goes_to_the_current_address(
    send_code: Callable[[APIClient], Response],
) -> None:
    response = send_code(make_auth_client(make_recovery_user()))

    assert response.status_code == 204
    assert mail.outbox[0].to == [ADDRESS]
    assert only_code()


def test_send_code_without_an_address_is_refused(
    send_code: Callable[[APIClient], Response],
) -> None:
    response = send_code(make_auth_client(make_user(username="old")))

    assert response.status_code == 409
    assert response.data["error_code"] == "RECOVERY_EMAIL_NOT_SET"
    assert mail.outbox == []


def test_send_code_for_a_confirmed_address_is_refused(
    send_code: Callable[[APIClient], Response],
) -> None:
    client = make_auth_client(make_recovery_user())
    send_code(client)
    _confirm(client, only_code())
    sent = len(mail.outbox)

    response = send_code(client)

    assert response.status_code == 409
    assert response.data["error_code"] == "RECOVERY_EMAIL_ALREADY_CONFIRMED"
    assert len(mail.outbox) == sent


def test_send_code_over_the_limit_says_how_long_to_wait(
    send_code: Callable[[APIClient], Response],
) -> None:
    client = make_auth_client(make_recovery_user())
    send_code(client)

    response = send_code(client)

    assert response.status_code == 429
    assert response.data["error_code"] == "EMAIL_CODE_RATE_LIMITED"
    assert 0 < response.data["retry_after_seconds"] <= 60
    assert len(mail.outbox) == 1


def test_the_limit_is_shared_with_the_recovery_request(
    send_code: Callable[[APIClient], Response],
    django_capture_on_commit_callbacks: CaptureOnCommit,
) -> None:
    """It protects the mailbox, so both purposes count against the same address."""
    send_code(make_auth_client(make_recovery_user()))

    with django_capture_on_commit_callbacks(execute=True):
        APIClient().post(RECOVERY_REQUEST_URL, {"email": ADDRESS}, format="json")

    assert len(mail.outbox) == 1


# ─── Confirm ────────────────────────────────────────────────────────────────────────────────


def test_confirm_marks_the_address(send_code: Callable[[APIClient], Response]) -> None:
    user = make_recovery_user()
    client = make_auth_client(user)
    send_code(client)

    response = _confirm(client, only_code())

    assert response.status_code == 200
    assert response.data == {"recovery_email": ADDRESS, "recovery_email_confirmed": True}
    assert client.get(PROFILE_URL).data["recovery_email_confirmed"] is True


def test_wrong_code_gives_the_generic_error(send_code: Callable[[APIClient], Response]) -> None:
    client = make_auth_client(make_recovery_user())
    send_code(client)

    response = _confirm(client, wrong_code(only_code()))

    assert response.status_code == 400
    assert response.data["error_code"] == "INVALID_EMAIL_CODE"


def test_used_code_does_not_work_twice(send_code: Callable[[APIClient], Response]) -> None:
    client = make_auth_client(make_recovery_user())
    send_code(client)
    code = only_code()
    _confirm(client, code)

    assert _confirm(client, code).status_code == 400


def test_expired_code_does_not_work(send_code: Callable[[APIClient], Response]) -> None:
    client = make_auth_client(make_recovery_user())
    send_code(client)
    EmailCode.objects.update(expires_at=timezone.now() - timedelta(seconds=1))

    assert _confirm(client, only_code()).status_code == 400


def test_five_wrong_attempts_kill_the_code(send_code: Callable[[APIClient], Response]) -> None:
    client = make_auth_client(make_recovery_user())
    send_code(client)
    code = only_code()

    for _ in range(5):
        _confirm(client, wrong_code(code))

    assert _confirm(client, code).status_code == 400


def test_a_new_code_replaces_the_previous_one(
    send_code: Callable[[APIClient], Response],
) -> None:
    client = make_auth_client(make_recovery_user())
    send_code(client)
    old = only_code()
    EmailSendLedger.objects.all().delete()

    send_code(client)
    new = only_code()

    assert EmailCode.objects.count() == 1
    if old != new:
        assert _confirm(client, old).status_code == 400
    assert _confirm(client, new).status_code == 200


def test_a_recovery_code_does_not_confirm_the_address(
    django_capture_on_commit_callbacks: CaptureOnCommit,
) -> None:
    client = make_auth_client(make_recovery_user())
    with django_capture_on_commit_callbacks(execute=True):
        APIClient().post(RECOVERY_REQUEST_URL, {"email": ADDRESS}, format="json")

    assert _confirm(client, code_for("ana")).status_code == 400


# ─── Who may call ───────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("url", "body"),
    [
        (SET_URL, {"recovery_email": NEW_ADDRESS, "current_password": "secret1"}),
        (SEND_URL, {}),
        (CONFIRM_URL, {"code": "123456"}),
    ],
)
def test_google_only_accounts_do_not_have_this_feature(url: str, body: dict[str, str]) -> None:
    response = _google_only_client().post(url, body, format="json")

    assert response.status_code == 409
    assert response.data["error_code"] == "PASSWORD_NOT_SET"


@pytest.mark.parametrize("url", [SET_URL, SEND_URL, CONFIRM_URL])
def test_anonymous_callers_are_refused(url: str) -> None:
    assert APIClient().post(url, {}, format="json").status_code == 401
