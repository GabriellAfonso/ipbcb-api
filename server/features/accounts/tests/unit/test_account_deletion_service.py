"""AccountDeletionService on fakes (specs/021-user-account US1/US2)."""

import pytest

from core.application.dtos.account_dtos import AccountDeletionDTO
from core.domain.exceptions import (
    AccountDeletionBlockedError,
    ConfirmationMethodError,
    GoogleAccountMismatchError,
    InvalidGoogleConfirmationError,
    InvalidGoogleTokenError,
    InvalidPasswordError,
    UnverifiedGoogleEmailError,
)
from features.accounts.models.user import User
from features.accounts.services.account_deletion_service import AccountDeletionService
from features.accounts.tests.fakes import (
    FakeGoogleAccountResolver,
    FakeRefreshTokenRepository,
    RecordingPasswordCheck,
    RecordingUserRepository,
    unsaved_user,
)

# transaction.atomic needs a connection even though every repository here is a fake.
pytestmark = pytest.mark.django_db


class _Harness:
    def __init__(self, google: FakeGoogleAccountResolver | None = None) -> None:
        self.users = RecordingUserRepository()
        self.tokens = FakeRefreshTokenRepository()
        self.google = google or FakeGoogleAccountResolver()
        self.check = RecordingPasswordCheck()
        self.service = AccountDeletionService(
            user_repository=self.users,
            refresh_token_repository=self.tokens,
            google_resolver=self.google,
        )

    def delete_confirmed(self, user: User, **fields: str) -> None:
        self.service.delete_confirmed(user, AccountDeletionDTO(**fields), self.check)

    def assert_deleted(self, user: User) -> None:
        assert self.users.deleted == [user]
        assert self.tokens.revoked == [user.pk]

    def assert_untouched(self) -> None:
        assert self.users.deleted == []
        assert self.tokens.revoked == []


class TestPasswordAccount:
    def test_right_password_deletes_and_revokes(self) -> None:
        harness, user = _Harness(), unsaved_user()
        harness.delete_confirmed(user, password="secret1")
        harness.assert_deleted(user)
        assert harness.check.asked == ["secret1"]

    def test_wrong_password_changes_nothing(self) -> None:
        harness, user = _Harness(), unsaved_user()
        with pytest.raises(InvalidPasswordError):
            harness.delete_confirmed(user, password="wrong!")
        harness.assert_untouched()

    def test_google_token_instead_of_password_is_refused(self) -> None:
        harness, user = _Harness(), unsaved_user()
        with pytest.raises(ConfirmationMethodError, match="confirme com a senha"):
            harness.delete_confirmed(user, id_token="google-token")
        harness.assert_untouched()
        assert harness.google.tokens == []


class TestGoogleOnlyAccount:
    def test_token_of_the_same_account_deletes(self) -> None:
        user = unsaved_user(password=None)
        harness = _Harness(FakeGoogleAccountResolver(account=user))
        harness.delete_confirmed(user, id_token="google-token")
        harness.assert_deleted(user)

    def test_password_instead_of_token_is_refused(self) -> None:
        harness, user = _Harness(), unsaved_user(password=None)
        with pytest.raises(ConfirmationMethodError, match="confirme com o Google"):
            harness.delete_confirmed(user, password="secret1")
        harness.assert_untouched()
        assert harness.check.asked == []

    def test_token_of_another_account_is_a_mismatch(self) -> None:
        user = unsaved_user(password=None)
        harness = _Harness(FakeGoogleAccountResolver(account=unsaved_user("bia", None)))
        with pytest.raises(GoogleAccountMismatchError):
            harness.delete_confirmed(user, id_token="google-token")
        harness.assert_untouched()

    def test_token_of_no_account_is_a_mismatch(self) -> None:
        harness, user = _Harness(), unsaved_user(password=None)
        with pytest.raises(GoogleAccountMismatchError):
            harness.delete_confirmed(user, id_token="google-token")

    @pytest.mark.parametrize("error", [InvalidGoogleTokenError(), UnverifiedGoogleEmailError()])
    def test_bad_token_is_a_400_not_a_401(self, error: Exception) -> None:
        user = unsaved_user(password=None)
        harness = _Harness(FakeGoogleAccountResolver(error=error))
        with pytest.raises(InvalidGoogleConfirmationError):
            harness.delete_confirmed(user, id_token="google-token")
        harness.assert_untouched()


class TestSuperuser:
    def test_blocked_before_the_password_is_asked(self) -> None:
        harness, user = _Harness(), unsaved_user()
        user.is_superuser = True
        with pytest.raises(AccountDeletionBlockedError):
            harness.delete_confirmed(user, password="secret1")
        harness.assert_untouched()
        assert harness.check.asked == []

    def test_blocked_on_the_web_path_too(self) -> None:
        harness, user = _Harness(), unsaved_user()
        user.is_superuser = True
        with pytest.raises(AccountDeletionBlockedError):
            harness.service.delete_authenticated(user)
        harness.assert_untouched()


class TestWebGooglePath:
    def test_google_only_account_is_deleted(self) -> None:
        user = unsaved_user(password=None)
        harness = _Harness(FakeGoogleAccountResolver(account=user))
        harness.service.delete_by_google("google-token")
        harness.assert_deleted(user)

    def test_account_with_password_must_use_it(self) -> None:
        harness = _Harness(FakeGoogleAccountResolver(account=unsaved_user()))
        with pytest.raises(ConfirmationMethodError):
            harness.service.delete_by_google("google-token")
        harness.assert_untouched()

    def test_no_account_for_the_token(self) -> None:
        harness = _Harness()
        with pytest.raises(GoogleAccountMismatchError):
            harness.service.delete_by_google("google-token")
