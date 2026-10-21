"""Member access and access-request exceptions (specs/022-access-requests).

Their own module, like ``account_exceptions``, to keep ``core/domain/exceptions.py`` under 500
lines; that module re-exports every name here. Messages are in Portuguese: the app shows
``detail`` as is, and the field errors under the form field it highlights.
"""

from collections.abc import Collection
from uuid import UUID

from core.domain.base_exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitedError,
    ValidationError,
)


class _FieldValidationError(ValidationError):
    """A validation error that belongs to one form field."""

    field_name: str = ""

    def extra_context(self) -> dict[str, object]:
        return {"field_errors": {self.field_name: [str(self)]}}


class AccessRequestsBlockedError(PermissionDeniedError):
    """Leaders blocked this account from making requests (spec FR-008).

    >>> raise AccessRequestsBlockedError()
    """

    error_code: str = "ACCESS_REQUESTS_BLOCKED"

    def __init__(self) -> None:
        super().__init__("Pedidos de acesso indisponíveis. Fale com a liderança.")


class MemberAccessAlreadyGrantedError(ConflictError):
    """An ``access`` request from an account that already reaches member content.

    >>> raise MemberAccessAlreadyGrantedError()
    """

    error_code: str = "MEMBER_ACCESS_ALREADY_GRANTED"

    def __init__(self) -> None:
        super().__init__("Você já tem acesso de membro.")


class AccessRequestPendingError(ConflictError):
    """A request of the same type is still waiting for the leaders.

    >>> raise AccessRequestPendingError("access")
    """

    error_code: str = "ACCESS_REQUEST_PENDING"

    def __init__(self, request_type: str) -> None:
        super().__init__("Você já tem um pedido aguardando resposta.")
        self.request_type = request_type


class AccessRequestRateLimitedError(RateLimitedError):
    """Another request inside the rolling 24 hours (spec FR-007).

    >>> raise AccessRequestRateLimitedError(retry_after_seconds=3600)
    """

    error_code: str = "ACCESS_REQUEST_RATE_LIMITED"

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("Você já fez um pedido nas últimas 24 horas. Tente novamente mais tarde.")
        self.retry_after_seconds = retry_after_seconds

    def extra_context(self) -> dict[str, object]:
        return {"retry_after_seconds": self.retry_after_seconds}


class AccessRequestMessageRequiredError(_FieldValidationError):
    """A ``data_correction`` request without the text of the correction.

    >>> raise AccessRequestMessageRequiredError()
    """

    field_name = "message"

    def __init__(self) -> None:
        super().__init__("Descreva o que precisa ser corrigido.")


class AccessRequestNotFoundError(NotFoundError):
    """>>> raise AccessRequestNotFoundError(41)"""

    def __init__(self, request_id: int) -> None:
        super().__init__(f"Pedido não encontrado: id={request_id}.")
        self.request_id = request_id


class AccessRequestNotPendingError(ConflictError):
    """Deciding a request that was already approved or denied (spec FR-016).

    >>> raise AccessRequestNotPendingError(41, "approved")
    """

    error_code: str = "ACCESS_REQUEST_NOT_PENDING"

    def __init__(self, request_id: int, status: str) -> None:
        super().__init__("Este pedido já foi respondido.")
        self.request_id = request_id
        self.status = status


class ManagedAccountNotFoundError(NotFoundError):
    """No active account with this id in "Perfis".

    >>> raise ManagedAccountNotFoundError(UUID(int=1))
    """

    def __init__(self, user_id: UUID) -> None:
        super().__init__(f"Conta não encontrada: id={user_id}.")
        self.user_id = user_id


class RollMemberNotFoundError(_FieldValidationError):
    """Linking an account to a roll member that does not exist.

    >>> raise RollMemberNotFoundError(999)
    """

    field_name = "member_id"

    def __init__(self, member_id: int) -> None:
        super().__init__(f"Membro do rol não encontrado: id={member_id}.")
        self.member_id = member_id


class RollMemberAlreadyLinkedError(ConflictError):
    """The roll member is already linked to another account (one-to-one, spec 015).

    >>> raise RollMemberAlreadyLinkedError(12)
    """

    error_code: str = "MEMBER_ALREADY_LINKED"

    def __init__(self, member_id: int) -> None:
        super().__init__("Este membro já está vinculado a outra conta.")
        self.member_id = member_id


class MemberNotLinkedError(NotFoundError):
    """Reading one's own roll data with no roll record linked to the account.

    >>> raise MemberNotLinkedError()
    """

    error_code: str = "MEMBER_NOT_LINKED"

    def __init__(self) -> None:
        super().__init__("Sua conta não está vinculada a um membro do rol.")


class ProfileStatusFilterError(_FieldValidationError):
    """Unknown ``status`` filter on the "Perfis" list.

    >>> raise ProfileStatusFilterError("old", ["pending", "all"])
    """

    field_name = "status"

    def __init__(self, value: str, accepted: Collection[str]) -> None:
        super().__init__(f"Filtro 'status' inválido: {value!r}. Use um de: {', '.join(accepted)}.")
