"""DTOs of the account self-service use cases (specs/021-user-account)."""

from core.application.dtos.strict_base import StrictBaseModel


class PasswordChangeDTO(StrictBaseModel):
    """Validated by ``PasswordChangeSerializer`` first (length, confirmation)."""

    current_password: str
    new_password: str


class AccountDeletionDTO(StrictBaseModel):
    """Which field is required depends on the account, not on the request: the password when the
    account has one, the Google token when it does not (research R-05)."""

    password: str | None = None
    id_token: str | None = None
