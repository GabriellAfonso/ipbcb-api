"""RecoveryEmailService with its collaborators faked (specs/028-password-recovery US3)."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from conftest import make_user
from core.application.dtos.account_dtos import RecoveryEmailChangeDTO
from core.domain.exceptions import (
    EmailCodeRateLimitedError,
    InvalidEmailCodeError,
    InvalidPasswordError,
    PasswordNotSetError,
)
from features.accounts.models.user import User
from features.accounts.repositories.email_code_repository import EmailCodeRepositoryImpl
from features.accounts.repositories.profile_repository import ProfileRepositoryImpl
from features.accounts.services.recovery_email_service import RecoveryEmailService
from features.accounts.tests.fakes import (
    FixedClock,
    RecordingEmailSender,
    RecordingPasswordCheck,
)

ADDRESS = "ana@example.com"
START = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)

pytestmark = pytest.mark.django_db

CaptureOnCommit = Callable[..., Any]


class _Harness:
    def __init__(self) -> None:
        self.sender = RecordingEmailSender()
        self.clock = FixedClock(START)
        self.service = RecoveryEmailService(
            profile_repository=ProfileRepositoryImpl(),
            email_code_repository=EmailCodeRepositoryImpl(),
            email_sender=self.sender,
            clock=self.clock,
        )

    def code(self) -> str:
        return self.sender.messages[-1].body.split("\n\n")[1]


@pytest.fixture
def harness() -> _Harness:
    return _Harness()


@pytest.fixture
def user() -> User:
    account = make_user(username="ana", password="secret1")  # nosec B106
    account.profile.recovery_email = ADDRESS
    account.profile.save()
    return account


def _dto(address: str = "novo@example.com", password: str = "secret1") -> RecoveryEmailChangeDTO:  # nosec B107
    return RecoveryEmailChangeDTO(recovery_email=address, current_password=password)


def _send(harness: _Harness, user: User, capture: CaptureOnCommit) -> None:
    with capture(execute=True):
        harness.service.send_confirmation_code(user)


def test_change_asks_the_password_before_anything(harness: _Harness, user: User) -> None:
    check = RecordingPasswordCheck(correct="other")

    with pytest.raises(InvalidPasswordError):
        harness.service.change_email(user, _dto(), check)

    assert check.asked == ["secret1"]
    assert user.profile.recovery_email == ADDRESS


def test_google_only_account_is_refused_without_asking_the_password(harness: _Harness) -> None:
    account = make_user(username="google")
    account.set_unusable_password()
    account.save()
    check = RecordingPasswordCheck()

    with pytest.raises(PasswordNotSetError):
        harness.service.change_email(account, _dto(), check)

    assert check.asked == []


def test_change_writes_the_profile_and_not_the_user(harness: _Harness, user: User) -> None:
    profile = harness.service.change_email(user, _dto(), RecordingPasswordCheck())

    assert profile.recovery_email == "novo@example.com"
    user.refresh_from_db()
    assert user.email == ""


def test_confirm_records_the_moment(
    harness: _Harness, user: User, django_capture_on_commit_callbacks: CaptureOnCommit
) -> None:
    _send(harness, user, django_capture_on_commit_callbacks)

    profile = harness.service.confirm_email(user, harness.code())

    assert profile.recovery_email_confirmed_at == START


def test_code_expires_after_fifteen_minutes(
    harness: _Harness, user: User, django_capture_on_commit_callbacks: CaptureOnCommit
) -> None:
    _send(harness, user, django_capture_on_commit_callbacks)
    code = harness.code()
    harness.clock.current = START + timedelta(minutes=15)

    with pytest.raises(InvalidEmailCodeError):
        harness.service.confirm_email(user, code)


def test_a_refused_send_writes_no_code_and_says_how_long(
    harness: _Harness, user: User, django_capture_on_commit_callbacks: CaptureOnCommit
) -> None:
    _send(harness, user, django_capture_on_commit_callbacks)
    code = harness.code()
    harness.clock.current = START + timedelta(seconds=10)

    with pytest.raises(EmailCodeRateLimitedError) as caught:
        harness.service.send_confirmation_code(user)

    assert caught.value.retry_after_seconds == 50
    harness.service.confirm_email(user, code)
