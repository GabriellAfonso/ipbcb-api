"""Account self-service exceptions: password change, account deletion
(specs/021-user-account) and password recovery (specs/028-password-recovery).

Their own module, like ``event_exceptions``, to keep ``core/domain/exceptions.py`` under 500
lines; that module re-exports every name here. Messages are in Portuguese: the app shows
``detail`` as is. None of them is an ``AuthenticationError``: a 401 tells the app the session
expired, and a wrong confirmation does not end the session (spec FR-015).
"""

from core.domain.base_exceptions import (
    ConflictError,
    PermissionDeniedError,
    RateLimitedError,
    ValidationError,
)


class InvalidPasswordError(ValidationError):
    """The password given to confirm an account action is not the account's.

    >>> raise InvalidPasswordError()
    """

    error_code: str = "INVALID_PASSWORD"

    def __init__(self) -> None:
        super().__init__("Senha incorreta.")


class PasswordNotSetError(ConflictError):
    """Password change asked by an account whose password is unusable (created by Google).

    >>> raise PasswordNotSetError()
    """

    error_code: str = "PASSWORD_NOT_SET"

    def __init__(self) -> None:
        super().__init__("Esta conta não tem senha.")


class ConfirmationMethodError(ValidationError):
    """Deletion sent without the confirmation this account uses: the password when it has one,
    a Google token when it does not.

    >>> raise ConfirmationMethodError(has_password=True)
    """

    def __init__(self, has_password: bool) -> None:
        if has_password:
            super().__init__("Esta conta tem senha: confirme com a senha.")
        else:
            super().__init__("Esta conta não tem senha: confirme com o Google.")
        self.has_password = has_password


class InvalidGoogleConfirmationError(ValidationError):
    """The Google token sent to confirm a deletion failed verification (signature, audience,
    expiry or unverified e-mail). A 400, unlike the 401 the same failure gets at sign-in.

    >>> raise InvalidGoogleConfirmationError()
    """

    error_code: str = "INVALID_GOOGLE_TOKEN"

    def __init__(self) -> None:
        super().__init__("Não foi possível confirmar com o Google. Tente novamente.")


class GoogleAccountMismatchError(PermissionDeniedError):
    """A valid Google token that resolves to another account, or to none.

    >>> raise GoogleAccountMismatchError()
    """

    error_code: str = "GOOGLE_ACCOUNT_MISMATCH"

    def __init__(self) -> None:
        super().__init__("A conta Google não corresponde a esta conta.")


class AccountDeletionBlockedError(ConflictError):
    """Superusers cannot delete themselves, so the Django admin is never lost by accident.

    >>> raise AccountDeletionBlockedError()
    """

    error_code: str = "ACCOUNT_DELETION_BLOCKED"

    def __init__(self) -> None:
        super().__init__(
            "Esta conta não pode ser excluída pelo app. Fale com a liderança da igreja."
        )


class InvalidEmailCodeError(ValidationError):
    """A wrong, expired or used e-mail code: deliberately one error for all of them, with no
    offending value, so a caller guessing codes learns nothing from the answer.

    >>> raise InvalidEmailCodeError()
    """

    error_code: str = "INVALID_EMAIL_CODE"

    def __init__(self) -> None:
        super().__init__("Código inválido ou expirado.")


class EmailCodeRateLimitedError(RateLimitedError):
    """A signed-in person over the per-address send limit. The public request never raises
    this: it answers the same whatever happened.

    >>> raise EmailCodeRateLimitedError(retry_after_seconds=60)
    """

    error_code: str = "EMAIL_CODE_RATE_LIMITED"

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("Aguarde um pouco antes de pedir outro código.")
        self.retry_after_seconds = retry_after_seconds

    def extra_context(self) -> dict[str, object]:
        return {"retry_after_seconds": self.retry_after_seconds}


class RecoveryEmailNotSetError(ConflictError):
    """A confirmation code asked by an account with no recovery e-mail.

    >>> raise RecoveryEmailNotSetError()
    """

    error_code: str = "RECOVERY_EMAIL_NOT_SET"

    def __init__(self) -> None:
        super().__init__("Esta conta não tem e-mail de recuperação.")


class RecoveryEmailAlreadyConfirmedError(ConflictError):
    """A confirmation code asked for an address already confirmed.

    >>> raise RecoveryEmailAlreadyConfirmedError()
    """

    error_code: str = "RECOVERY_EMAIL_ALREADY_CONFIRMED"

    def __init__(self) -> None:
        super().__init__("Este e-mail já está confirmado.")
