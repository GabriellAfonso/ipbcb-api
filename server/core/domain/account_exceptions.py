"""Account self-service exceptions: password change and account deletion
(specs/021-user-account).

Their own module, like ``event_exceptions``, to keep ``core/domain/exceptions.py`` under 500
lines; that module re-exports every name here. Messages are in Portuguese: the app shows
``detail`` as is. None of them is an ``AuthenticationError``: a 401 tells the app the session
expired, and a wrong confirmation does not end the session (spec FR-015).
"""

from core.domain.base_exceptions import ConflictError, PermissionDeniedError, ValidationError


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
