"""Base classes of every domain exception, one per HTTP family (spec 001).

Their own module so ``gallery_exceptions`` can build on them without importing
``exceptions``, which re-exports both (specs/015-gallery-member-tags research R-10).
"""


class DomainError(Exception):
    """Base exception for all domain errors.

    Every subclass inherits ``error_code`` for machine-readable identification
    and can override ``extra_context()`` to attach domain data to error responses.

    >>> raise DomainError("something broke")
    """

    error_code: str = "DOMAIN_ERROR"

    def extra_context(self) -> dict[str, object]:
        """Return additional domain data to include in the error response."""
        return {}


class NotFoundError(DomainError):
    """Raised when a requested entity does not exist."""

    error_code: str = "NOT_FOUND"


class ConflictError(DomainError):
    """Raised when an operation conflicts with existing state."""

    error_code: str = "CONFLICT"


class ValidationError(DomainError):
    """Raised when input validation fails at the domain level."""

    error_code: str = "VALIDATION_ERROR"


class AuthenticationError(DomainError):
    """Raised when authentication fails."""

    error_code: str = "AUTHENTICATION_FAILED"


class PermissionDeniedError(DomainError):
    """Raised when an authenticated caller lacks the permission an operation requires.

    Same ``error_code`` DRF's own ``PermissionDenied`` produces, so clients see one code for
    a denial whether it came from a permission class or from a service.

    >>> raise PermissionDeniedError("Leaders only: 'members'")
    """

    error_code: str = "PERMISSION_DENIED"
