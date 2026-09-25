import logging

from django.conf import settings
from pydantic import ValidationError as PydanticValidationError
from rest_framework import status
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied,
    Throttled,
    ValidationError as DRFValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler

from core.domain.exceptions import (
    AuthenticationError,
    ConflictError,
    DomainError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)

logger = logging.getLogger(__name__)

_DOMAIN_STATUS_MAP: dict[type[DomainError], int] = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ValidationError: status.HTTP_400_BAD_REQUEST,
    ConflictError: status.HTTP_409_CONFLICT,
    AuthenticationError: status.HTTP_401_UNAUTHORIZED,
    PermissionDeniedError: status.HTTP_403_FORBIDDEN,
}


def _status_for_domain(exc: DomainError) -> int:
    for cls, http_status in _DOMAIN_STATUS_MAP.items():
        if isinstance(exc, cls):
            return http_status
    return status.HTTP_500_INTERNAL_SERVER_ERROR


def build_canonical_error(
    error_code: str,
    detail: str,
    field_errors: dict[str, list[str]] | None = None,
    **extra: object,
) -> dict[str, object]:
    """Return the response body every error in this API is shaped like.

    Public because responses are also built outside the DRF exception handler — the
    django-axes lockout in ``core.http.lockout`` is produced by middleware, which never
    reaches this handler, and must not carry a second copy of the shape.

    >>> build_canonical_error("NOT_FOUND", "Song not found: id=7")
    {'error_code': 'NOT_FOUND', 'detail': 'Song not found: id=7'}
    """
    body: dict[str, object] = {"error_code": error_code, "detail": detail}
    if field_errors:
        body["field_errors"] = field_errors
    body.update(extra)
    return body


def _handle_domain_exception(exc: DomainError) -> Response:
    http_status = _status_for_domain(exc)
    body = build_canonical_error(exc.error_code, str(exc))
    body.update(exc.extra_context())
    return Response(body, status=http_status)


def _reshape_drf_validation(response: Response) -> Response:
    """Convert DRF ValidationError response.data into canonical format."""
    data = response.data

    if isinstance(data, dict):
        # Field-level errors: {"field": ["msg", ...]}
        field_errors = {k: v if isinstance(v, list) else [v] for k, v in data.items()}
        body = build_canonical_error(
            "VALIDATION_ERROR", "Validation failed.", field_errors=field_errors
        )
    elif isinstance(data, list):
        body = build_canonical_error("VALIDATION_ERROR", " ".join(str(e) for e in data))
    else:
        body = build_canonical_error("VALIDATION_ERROR", str(data))

    response.data = body
    return response


# Order matters: these are matched by inheritance, first hit wins, and NotAuthenticated is
# itself a subclass of AuthenticationFailed. Most specific first.
_DRF_ERROR_CODE_MAP: dict[type[Exception], str] = {
    NotAuthenticated: "NOT_AUTHENTICATED",
    AuthenticationFailed: "AUTHENTICATION_FAILED",
    PermissionDenied: "PERMISSION_DENIED",
    Throttled: "THROTTLED",
}

_DRF_DETAIL_OVERRIDES: dict[type[Exception], str] = {
    NotAuthenticated: "Faça login para ter acesso.",
    AuthenticationFailed: "Token inválido ou expirado. Faça login novamente.",
}


def _match_by_type[T](exc: Exception, table: dict[type[Exception], T]) -> T | None:
    """First entry whose class ``exc`` is an instance of, or None.

    Matching on ``type(exc)`` misses subclasses, and third-party packages raise those:
    SimpleJWT signals a bad token with ``InvalidToken``, a subclass of
    ``AuthenticationFailed``, which used to fall through to "UNKNOWN". Same approach
    ``_status_for_domain`` already takes for the domain exceptions.
    """
    for cls, value in table.items():
        if isinstance(exc, cls):
            return value
    return None


def _flatten_detail(detail: object) -> str:
    """Reduce a DRF detail to the string the canonical body promises.

    SimpleJWT wraps its message in ``{"detail": ..., "code": ...}``. Copied through as-is,
    a client reading ``detail`` as text renders the raw JSON on screen.
    """
    if isinstance(detail, dict):
        inner = detail.get("detail")
        return str(inner) if inner is not None else str(detail)
    return str(detail)


def _reshape_drf_exception(exc: Exception, response: Response) -> Response:
    if isinstance(exc, DRFValidationError):
        return _reshape_drf_validation(response)

    error_code = _match_by_type(exc, _DRF_ERROR_CODE_MAP) or "UNKNOWN"
    detail = _match_by_type(exc, _DRF_DETAIL_OVERRIDES)

    if detail is None:
        detail = _flatten_detail(getattr(exc, "detail", "An error occurred."))

    response.data = build_canonical_error(error_code, detail)
    return response


def _handle_pydantic_validation(exc: PydanticValidationError) -> Response:
    field_errors: dict[str, list[str]] = {}
    for err in exc.errors():
        loc = ".".join(str(part) for part in err["loc"])
        field_errors.setdefault(loc, []).append(err["msg"])
    body = build_canonical_error(
        "VALIDATION_ERROR", "Validation failed.", field_errors=field_errors
    )
    return Response(body, status=status.HTTP_400_BAD_REQUEST)


def _log_response(exc: Exception, response: Response) -> None:
    if response.status_code >= 500:
        logger.error(
            "Server error %s: %s",
            response.data.get("error_code", "UNKNOWN"),
            response.data.get("detail", ""),
            exc_info=exc,
        )
    else:
        logger.warning(
            "Client error %s %s: %s",
            response.status_code,
            response.data.get("error_code", "UNKNOWN"),
            response.data.get("detail", ""),
        )


def custom_exception_handler(exc: Exception, context: dict[str, object]) -> Response:
    # 1. Domain exceptions
    if isinstance(exc, DomainError):
        response = _handle_domain_exception(exc)
        _log_response(exc, response)
        return response

    # 2. Pydantic validation errors (safety net for unhandled Pydantic errors)
    if isinstance(exc, PydanticValidationError):
        response = _handle_pydantic_validation(exc)
        _log_response(exc, response)
        return response

    # 3. DRF-known exceptions
    drf_response = exception_handler(exc, context)
    if drf_response is not None:
        response = drf_response
        response = _reshape_drf_exception(exc, response)
        _log_response(exc, response)
        return response

    # 4. Unhandled exceptions — structured 500, never None
    detail = str(exc) if settings.DEBUG else "An unexpected error occurred."
    body = build_canonical_error("INTERNAL_ERROR", detail)
    response = Response(body, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    _log_response(exc, response)
    return response
