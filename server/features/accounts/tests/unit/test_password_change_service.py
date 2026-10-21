"""PasswordChangeService on fakes (specs/021-user-account US3)."""

import pytest
from rest_framework_simplejwt.tokens import AccessToken

from conftest import make_user
from core.application.dtos.account_dtos import PasswordChangeDTO
from core.domain.exceptions import InvalidPasswordError, PasswordNotSetError
from features.accounts.services.password_change_service import PasswordChangeService
from features.accounts.tests.fakes import (
    FakeRefreshTokenRepository,
    RecordingPasswordCheck,
    RecordingUserRepository,
    unsaved_user,
)

pytestmark = pytest.mark.django_db

DTO = PasswordChangeDTO(current_password="secret1", new_password="new-secret")


def _service() -> tuple[PasswordChangeService, RecordingUserRepository, FakeRefreshTokenRepository]:
    users, tokens = RecordingUserRepository(), FakeRefreshTokenRepository()
    return (
        PasswordChangeService(user_repository=users, refresh_token_repository=tokens),
        users,
        tokens,
    )


def test_changes_revokes_and_returns_a_pair_for_the_new_password() -> None:
    service, users, tokens = _service()
    user = make_user(username="ana", password="secret1")

    pair = service.change_password(user, DTO, RecordingPasswordCheck())

    assert users.passwords == [(user, "new-secret")]
    assert tokens.revoked == [user.pk]
    # The pair carries the hash of the new password, so CHECK_REVOKE_TOKEN accepts it.
    assert AccessToken(pair.access)["user_id"] == str(user.pk)  # type: ignore[arg-type]
    assert user.check_password("new-secret")


def test_wrong_current_password_changes_nothing() -> None:
    service, users, tokens = _service()
    with pytest.raises(InvalidPasswordError):
        service.change_password(unsaved_user(), DTO, RecordingPasswordCheck(correct="other1"))
    assert users.passwords == []
    assert tokens.revoked == []


def test_account_without_password_is_refused_before_any_check() -> None:
    service, users, _ = _service()
    check = RecordingPasswordCheck()
    with pytest.raises(PasswordNotSetError):
        service.change_password(unsaved_user(password=None), DTO, check)
    assert check.asked == []
    assert users.passwords == []
