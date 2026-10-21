import logging

from django.db import transaction

from core.application.dtos.account_dtos import PasswordChangeDTO
from core.application.dtos.auth_dtos import TokenDTO
from core.domain.exceptions import PasswordNotSetError
from features.accounts.auth.jwt import get_tokens_for_user
from features.accounts.models.user import User
from features.accounts.repositories.interfaces import RefreshTokenRepository, UserRepository
from features.accounts.services.password_check import PasswordCheck

logger = logging.getLogger(__name__)


class PasswordChangeService:
    """Changes the password and signs out every other session (specs/021-user-account)."""

    def __init__(
        self, user_repository: UserRepository, refresh_token_repository: RefreshTokenRepository
    ) -> None:
        self._user_repo = user_repository
        self._token_repo = refresh_token_repository

    def change_password(
        self, user: User, dto: PasswordChangeDTO, verify_password: PasswordCheck
    ) -> TokenDTO:
        """Return the only pair that still works once the password has changed.

        Every access token issued before dies with the old password hash (``CHECK_REVOKE_TOKEN``)
        — the caller's included — and every refresh token is blacklisted. The new pair is built
        from the user after the change (Business Rule 15), so it carries the new hash.

        >>> service.change_password(user, PasswordChangeDTO(...), check).access
        'eyJhbGciOi...'
        """
        if not user.has_usable_password():
            raise PasswordNotSetError()
        verify_password(dto.current_password)
        with transaction.atomic():
            self._user_repo.set_password(user, dto.new_password)
            revoked = self._token_repo.revoke_all(user.pk)
        logger.info("password_changed", extra={"user_id": str(user.pk), "revoked_tokens": revoked})
        return get_tokens_for_user(user)
