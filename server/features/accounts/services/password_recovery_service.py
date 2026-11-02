import logging
from collections.abc import Sequence
from datetime import datetime
from functools import partial

from django.db import transaction

from core.application.dtos.account_dtos import (
    PasswordRecoveryConfirmDTO,
    PasswordRecoveryRequestDTO,
)
from core.domain.exceptions import InvalidEmailCodeError
from core.time.clock import Clock
from features.accounts.domain.email_codes import (
    CODE_LIFETIME,
    EmailCodePurpose,
    address_key,
    code_digest,
    digests_match,
    generate_codes,
)
from features.accounts.domain.email_messages import recovery_message
from features.accounts.dtos import (
    AccountCodeDTO,
    EmailMessageDTO,
    NewEmailCodeDTO,
    PendingEmailCodeDTO,
)
from features.accounts.models.user import User
from features.accounts.repositories.interfaces import (
    AccountLockoutResetter,
    EmailCodeRepository,
    EmailSender,
    RefreshTokenRepository,
    UserRepository,
)

logger = logging.getLogger(__name__)

_PURPOSE = EmailCodePurpose.RECOVERY


class PasswordRecoveryService:
    """The public recovery flow (specs/028-password-recovery). Nothing here reveals to the caller
    whether an address has an account."""

    def __init__(
        self,
        user_repository: UserRepository,
        refresh_token_repository: RefreshTokenRepository,
        email_code_repository: EmailCodeRepository,
        email_sender: EmailSender,
        lockout_resetter: AccountLockoutResetter,
        clock: Clock,
    ) -> None:
        self._user_repo = user_repository
        self._token_repo = refresh_token_repository
        self._codes = email_code_repository
        self._sender = email_sender
        self._lockout = lockout_resetter
        self._clock = clock

    def request_codes(self, dto: PasswordRecoveryRequestDTO) -> None:
        """Send the address one message with a code per matching account, unless it is over its
        limit. Returns nothing, so no caller can answer differently by outcome. The slot is claimed
        even for an unknown address: both paths then do the same work and obey the same limit.

        >>> service.request_codes(PasswordRecoveryRequestDTO(email="ana@example.com"))
        """
        now = self._clock.now()
        with transaction.atomic():
            if self._codes.claim_send_slot(address_key(dto.email), now):
                return
            accounts = self._user_repo.recovery_accounts(dto.email)
            if not accounts:
                return
            message = self._issue_codes(dto.email, accounts, now)
            transaction.on_commit(partial(self._sender.send, message))

    def confirm(self, dto: PasswordRecoveryConfirmDTO) -> None:
        """Set the new password of the account the code belongs to, or raise
        ``InvalidEmailCodeError``. Raised after the transaction: raising inside would roll back
        the wrong attempt it just counted, leaving guesses unlimited (research R-02).

        The lockout is cleared last, otherwise the person stays locked out with the new password.

        >>> service.confirm(PasswordRecoveryConfirmDTO(email="ana@example.com", code="123456",
        ...                                            new_password="nova-senha"))
        """
        user = self._apply_code(dto)
        if user is None:
            raise InvalidEmailCodeError()
        self._lockout.reset(user.username)

    def _issue_codes(
        self, address: str, accounts: Sequence[User], now: datetime
    ) -> EmailMessageDTO:
        codes = generate_codes(len(accounts))
        self._codes.replace_codes(
            [
                NewEmailCodeDTO(
                    user_id=account.pk,
                    purpose=_PURPOSE,
                    address=address,
                    code_digest=code_digest(_PURPOSE, address, code),
                    expires_at=now + CODE_LIFETIME,
                )
                for account, code in zip(accounts, codes, strict=True)
            ]
        )
        return recovery_message(
            address,
            [
                AccountCodeDTO(username=account.username, code=code)
                for account, code in zip(accounts, codes, strict=True)
            ],
        )

    def _apply_code(self, dto: PasswordRecoveryConfirmDTO) -> User | None:
        with transaction.atomic():
            pending = self._codes.lock_live_for_address(_PURPOSE, dto.email, self._clock.now())
            matched = _find_match(pending, code_digest(_PURPOSE, dto.email, dto.code))
            if matched is None:
                self._codes.count_failure_for_address(_PURPOSE, dto.email)
                return None
            self._codes.consume(_PURPOSE, matched.user_id)
            # Re-checked: the account may have been deactivated or changed since the request.
            user = self._user_repo.get_recovery_account(matched.user_id, dto.email)
            if user is None:
                return None
            self._user_repo.set_password(user, dto.new_password)
            revoked = self._token_repo.revoke_all(user.pk)
        logger.info(
            "password_recovered", extra={"user_id": str(user.pk), "revoked_tokens": revoked}
        )
        return user


def _find_match(pending: Sequence[PendingEmailCodeDTO], digest: str) -> PendingEmailCodeDTO | None:
    return next((code for code in pending if digests_match(code.code_digest, digest)), None)
