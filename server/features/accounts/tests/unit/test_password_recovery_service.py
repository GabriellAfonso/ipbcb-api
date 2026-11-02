"""PasswordRecoveryService with its collaborators faked (specs/028-password-recovery US1)."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from conftest import make_user
from core.application.dtos.account_dtos import (
    PasswordRecoveryConfirmDTO,
    PasswordRecoveryRequestDTO,
)
from core.domain.exceptions import InvalidEmailCodeError
from features.accounts.models.user import User
from features.accounts.repositories.email_code_repository import EmailCodeRepositoryImpl
from features.accounts.repositories.user_repository import UserRepositoryImpl
from features.accounts.services.password_recovery_service import PasswordRecoveryService
from features.accounts.tests.fakes import (
    FakeRefreshTokenRepository,
    FixedClock,
    RecordingEmailSender,
    RecordingLockoutResetter,
)

ADDRESS = "ana@example.com"
START = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)

pytestmark = pytest.mark.django_db

CaptureOnCommit = Callable[..., Any]


class _Harness:
    def __init__(self) -> None:
        self.sender = RecordingEmailSender()
        self.tokens = FakeRefreshTokenRepository()
        self.lockout = RecordingLockoutResetter()
        self.clock = FixedClock(START)
        self.service = PasswordRecoveryService(
            user_repository=UserRepositoryImpl(),
            refresh_token_repository=self.tokens,
            email_code_repository=EmailCodeRepositoryImpl(),
            email_sender=self.sender,
            lockout_resetter=self.lockout,
            clock=self.clock,
        )

    def code(self) -> str:
        return self.sender.messages[-1].body.split("ana: ")[1][:6]


@pytest.fixture
def harness() -> _Harness:
    return _Harness()


@pytest.fixture
def user() -> User:
    account = make_user(username="ana", password="secret1")  # nosec B106
    account.profile.recovery_email = ADDRESS
    account.profile.save()
    return account


def _dto(code: str) -> PasswordRecoveryConfirmDTO:
    return PasswordRecoveryConfirmDTO(email=ADDRESS, code=code, new_password="nova-senha")


def _request(harness: _Harness, capture: CaptureOnCommit) -> None:
    with capture(execute=True):
        harness.service.request_codes(PasswordRecoveryRequestDTO(email=ADDRESS))


def test_nothing_is_sent_before_the_commit(
    harness: _Harness, user: User, django_capture_on_commit_callbacks: CaptureOnCommit
) -> None:
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        harness.service.request_codes(PasswordRecoveryRequestDTO(email=ADDRESS))

    assert harness.sender.messages == []
    assert len(callbacks) == 1


def test_confirm_revokes_and_clears_the_lockout(
    harness: _Harness, user: User, django_capture_on_commit_callbacks: CaptureOnCommit
) -> None:
    _request(harness, django_capture_on_commit_callbacks)

    harness.service.confirm(_dto(harness.code()))

    user.refresh_from_db()
    assert user.check_password("nova-senha")
    assert harness.tokens.revoked == [user.pk]
    assert harness.lockout.usernames == ["ana"]


def test_wrong_code_changes_nothing(
    harness: _Harness, user: User, django_capture_on_commit_callbacks: CaptureOnCommit
) -> None:
    _request(harness, django_capture_on_commit_callbacks)
    wrong = "000000" if harness.code() != "000000" else "000001"

    with pytest.raises(InvalidEmailCodeError):
        harness.service.confirm(_dto(wrong))

    user.refresh_from_db()
    assert user.check_password("secret1")
    assert harness.tokens.revoked == []
    assert harness.lockout.usernames == []


def test_code_expires_after_fifteen_minutes(
    harness: _Harness, user: User, django_capture_on_commit_callbacks: CaptureOnCommit
) -> None:
    _request(harness, django_capture_on_commit_callbacks)
    code = harness.code()
    harness.clock.current = START + timedelta(minutes=15)

    with pytest.raises(InvalidEmailCodeError):
        harness.service.confirm(_dto(code))


def test_code_still_works_just_before_expiry(
    harness: _Harness, user: User, django_capture_on_commit_callbacks: CaptureOnCommit
) -> None:
    _request(harness, django_capture_on_commit_callbacks)
    code = harness.code()
    harness.clock.current = START + timedelta(minutes=14, seconds=59)

    harness.service.confirm(_dto(code))


def test_requests_after_the_limit_window_send_again(
    harness: _Harness, user: User, django_capture_on_commit_callbacks: CaptureOnCommit
) -> None:
    _request(harness, django_capture_on_commit_callbacks)
    harness.clock.current = START + timedelta(seconds=59)
    _request(harness, django_capture_on_commit_callbacks)
    assert len(harness.sender.messages) == 1

    harness.clock.current = START + timedelta(seconds=60)
    _request(harness, django_capture_on_commit_callbacks)

    assert len(harness.sender.messages) == 2
