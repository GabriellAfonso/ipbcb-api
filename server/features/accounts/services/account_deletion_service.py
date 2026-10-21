import logging
from typing import Protocol

from django.db import transaction

from core.application.dtos.account_dtos import AccountDeletionDTO
from core.domain.exceptions import (
    AccountDeletionBlockedError,
    ConfirmationMethodError,
    GoogleAccountMismatchError,
    InvalidGoogleConfirmationError,
    InvalidGoogleTokenError,
    UnverifiedGoogleEmailError,
)
from features.accounts.models.user import User
from features.accounts.repositories.interfaces import RefreshTokenRepository, UserRepository
from features.accounts.services.password_check import PasswordCheck

logger = logging.getLogger(__name__)


class GoogleAccountResolver(Protocol):
    """What deletion needs from Google sign-in: the account a token opens (``GoogleAuthService``)."""

    def resolve_existing_account(self, token: str) -> User | None: ...


class AccountDeletionService:
    """Deletes an account at once, with no grace period (specs/021-user-account).

    The confirmation follows the account, never the way the person signed in: the password when
    the account has one, a Google token of the same account when it does not.
    """

    def __init__(
        self,
        user_repository: UserRepository,
        refresh_token_repository: RefreshTokenRepository,
        google_resolver: GoogleAccountResolver,
    ) -> None:
        self._user_repo = user_repository
        self._token_repo = refresh_token_repository
        self._google = google_resolver

    def delete_confirmed(
        self, user: User, dto: AccountDeletionDTO, verify_password: PasswordCheck
    ) -> None:
        """The in-app deletion: check what this account needs, then delete.

        The superuser block comes first, so a refused account is never asked for a password.

        >>> service.delete_confirmed(user, AccountDeletionDTO(password="secret1"), check)
        """
        self._ensure_deletable(user)
        if user.has_usable_password():
            if not dto.password:
                raise ConfirmationMethodError(has_password=True)
            verify_password(dto.password)
        else:
            if not dto.id_token:
                raise ConfirmationMethodError(has_password=False)
            self._ensure_same_account(user, dto.id_token)
        self._delete(user)

    def delete_authenticated(self, user: User) -> None:
        """Delete an account whose owner has just proven who they are (the web page's
        username + password form).

        >>> service.delete_authenticated(user)
        """
        self._ensure_deletable(user)
        self._delete(user)

    def delete_by_google(self, id_token: str) -> None:
        """The web page's Google path: the token identifies the account. Only for accounts
        without a password — one with a password must sign in with it.

        >>> service.delete_by_google("eyJhbGciOi...")
        """
        account = self._resolve(id_token)
        if account is None:
            raise GoogleAccountMismatchError()
        if account.has_usable_password():
            raise ConfirmationMethodError(has_password=True)
        self.delete_authenticated(account)

    def _ensure_deletable(self, user: User) -> None:
        if user.is_superuser:
            raise AccountDeletionBlockedError()

    def _ensure_same_account(self, user: User, id_token: str) -> None:
        # By identity, not by comparing e-mail text: the token must open *this* account.
        account = self._resolve(id_token)
        if account is None or account.pk != user.pk:
            raise GoogleAccountMismatchError()

    def _resolve(self, id_token: str) -> User | None:
        # A 400, not the sign-in 401: the session asking is still valid (spec FR-015).
        try:
            return self._google.resolve_existing_account(id_token)
        except (InvalidGoogleTokenError, UnverifiedGoogleEmailError):
            raise InvalidGoogleConfirmationError() from None

    def _delete(self, user: User) -> None:
        user_id = str(user.pk)
        with transaction.atomic():
            revoked = self._token_repo.revoke_all(user.pk)
            self._user_repo.delete(user)
        logger.info("account_deleted", extra={"user_id": user_id, "revoked_tokens": revoked})
