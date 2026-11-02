"""DTOs of the account self-service use cases (specs/021-user-account,
specs/028-password-recovery)."""

from pydantic import field_validator

from core.application.dtos.strict_base import StrictBaseModel
from core.application.email_address import normalize_email_address


class PasswordChangeDTO(StrictBaseModel):
    """Validated by ``PasswordChangeSerializer`` first (length, confirmation)."""

    current_password: str
    new_password: str


class AccountDeletionDTO(StrictBaseModel):
    """Which field is required depends on the account, not on the request: the password when the
    account has one, the Google token when it does not (research R-05)."""

    password: str | None = None
    id_token: str | None = None


class RecoveryEmailChangeDTO(StrictBaseModel):
    """Validated by ``RecoveryEmailChangeSerializer`` first. The address is normalised here.

    >>> RecoveryEmailChangeDTO(recovery_email=" A@B.com ", current_password="x").recovery_email
    'a@b.com'
    """

    recovery_email: str
    current_password: str

    _recovery_email = field_validator("recovery_email")(normalize_email_address)


class PasswordRecoveryRequestDTO(StrictBaseModel):
    """>>> PasswordRecoveryRequestDTO(email=" A@B.com ").email
    'a@b.com'
    """

    email: str

    _email = field_validator("email")(normalize_email_address)


class PasswordRecoveryConfirmDTO(StrictBaseModel):
    """Validated by ``PasswordRecoveryConfirmSerializer`` first (length, confirmation).

    >>> PasswordRecoveryConfirmDTO(email="A@B.com", code="1", new_password="x").email
    'a@b.com'
    """

    email: str
    code: str
    new_password: str

    _email = field_validator("email")(normalize_email_address)
