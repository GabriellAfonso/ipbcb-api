"""Account exceptions reach the client with the contract's status and code
(specs/021-user-account/contracts/account-api.md)."""

import pytest

from core.domain.exceptions import (
    AccountDeletionBlockedError,
    ConfirmationMethodError,
    DomainError,
    GoogleAccountMismatchError,
    InvalidGoogleConfirmationError,
    InvalidPasswordError,
    PasswordNotSetError,
)
from core.http.exceptions import custom_exception_handler


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (InvalidPasswordError(), 400, "INVALID_PASSWORD"),
        (PasswordNotSetError(), 409, "PASSWORD_NOT_SET"),
        (ConfirmationMethodError(has_password=True), 400, "VALIDATION_ERROR"),
        (InvalidGoogleConfirmationError(), 400, "INVALID_GOOGLE_TOKEN"),
        (GoogleAccountMismatchError(), 403, "GOOGLE_ACCOUNT_MISMATCH"),
        (AccountDeletionBlockedError(), 409, "ACCOUNT_DELETION_BLOCKED"),
    ],
)
def test_status_and_code(error: DomainError, status: int, code: str) -> None:
    response = custom_exception_handler(error, {})
    assert response.status_code == status
    assert response.data["error_code"] == code
    assert response.data["detail"] == str(error)


def test_confirmation_method_names_what_the_account_needs() -> None:
    assert "senha" in str(ConfirmationMethodError(has_password=True))
    assert "Google" in str(ConfirmationMethodError(has_password=False))
