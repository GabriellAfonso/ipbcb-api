from functools import partial

from django.db import transaction

from core.application.dtos.account_dtos import RecoveryEmailChangeDTO
from core.domain.exceptions import (
    EmailCodeRateLimitedError,
    InvalidEmailCodeError,
    PasswordNotSetError,
    RecoveryEmailAlreadyConfirmedError,
    RecoveryEmailNotSetError,
)
from core.time.clock import Clock
from features.accounts.domain.email_codes import (
    CODE_LIFETIME,
    EmailCodePurpose,
    address_key,
    code_digest,
    digests_match,
    generate_codes,
)
from features.accounts.domain.email_messages import confirmation_message
from features.accounts.dtos import NewEmailCodeDTO
from features.accounts.models.profile import Profile
from features.accounts.models.user import User
from features.accounts.repositories.interfaces import (
    EmailCodeRepository,
    EmailSender,
    ProfileRepository,
)
from features.accounts.services.password_check import PasswordCheck

_PURPOSE = EmailCodePurpose.CONFIRMATION


def _ensure_has_password(user: User) -> None:
    # Google-only accounts do not have this feature: they have no password to forget.
    if not user.has_usable_password():
        raise PasswordNotSetError()


class RecoveryEmailService:
    """The signed-in side of the recovery e-mail: set, change and confirm it
    (specs/028-password-recovery). It only ever writes ``Profile``: ``User.email`` stays written
    by Google alone, which is what keeps Google sign-in safe (constitution)."""

    def __init__(
        self,
        profile_repository: ProfileRepository,
        email_code_repository: EmailCodeRepository,
        email_sender: EmailSender,
        clock: Clock,
    ) -> None:
        self._profile_repo = profile_repository
        self._codes = email_code_repository
        self._sender = email_sender
        self._clock = clock

    def change_email(
        self, user: User, dto: RecoveryEmailChangeDTO, verify_password: PasswordCheck
    ) -> Profile:
        """Set or change the address. The password is required even the first time: a stolen
        session must not be able to add its own address and take the account. Sessions are kept.
        The address already stored is not a change, so its confirmation and codes stay.

        >>> service.change_email(user, RecoveryEmailChangeDTO(...), check).recovery_email
        'ana@example.com'
        """
        _ensure_has_password(user)
        verify_password(dto.current_password)
        profile, _ = self._profile_repo.get_or_create(user)
        if profile.recovery_email == dto.recovery_email:
            return profile
        with transaction.atomic():
            self._codes.delete_for_user(user.pk)
            return self._profile_repo.update(
                profile, recovery_email=dto.recovery_email, recovery_email_confirmed_at=None
            )

    def send_confirmation_code(self, user: User) -> None:
        """Send a code to the current address.

        >>> service.send_confirmation_code(user)
        """
        _ensure_has_password(user)
        profile, _ = self._profile_repo.get_or_create(user)
        if not profile.recovery_email:
            raise RecoveryEmailNotSetError()
        if profile.recovery_email_confirmed_at is not None:
            raise RecoveryEmailAlreadyConfirmedError()
        self._issue_code(user, profile.recovery_email)

    def confirm_email(self, user: User, code: str) -> Profile:
        """Mark the address confirmed, or raise ``InvalidEmailCodeError``, after the transaction
        so the wrong attempt stays counted (research R-02).

        >>> service.confirm_email(user, "123456").recovery_email_confirmed
        True
        """
        _ensure_has_password(user)
        profile, _ = self._profile_repo.get_or_create(user)
        if not self._apply_code(user, profile, code):
            raise InvalidEmailCodeError()
        return profile

    def _issue_code(self, user: User, address: str) -> None:
        now = self._clock.now()
        code = generate_codes(1)[0]
        with transaction.atomic():
            wait = self._codes.claim_send_slot(address_key(address), now)
            if wait:
                raise EmailCodeRateLimitedError(retry_after_seconds=wait)
            self._codes.replace_codes(
                [
                    NewEmailCodeDTO(
                        user_id=user.pk,
                        purpose=_PURPOSE,
                        address=address,
                        code_digest=code_digest(_PURPOSE, address, code),
                        expires_at=now + CODE_LIFETIME,
                    )
                ]
            )
            transaction.on_commit(partial(self._sender.send, confirmation_message(address, code)))

    def _apply_code(self, user: User, profile: Profile, code: str) -> bool:
        now = self._clock.now()
        digest = code_digest(_PURPOSE, profile.recovery_email, code)
        with transaction.atomic():
            pending = self._codes.lock_live_for_user(_PURPOSE, user.pk, now)
            if not any(digests_match(row.code_digest, digest) for row in pending):
                self._codes.count_failure_for_user(_PURPOSE, user.pk)
                return False
            self._codes.consume(_PURPOSE, user.pk)
            self._profile_repo.update(profile, recovery_email_confirmed_at=now)
        return True
