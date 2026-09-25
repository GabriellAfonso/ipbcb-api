import logging
from typing import Any
from unittest.mock import MagicMock

import pytest
from rest_framework.response import Response
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied,
    Throttled,
    ValidationError as DRFValidationError,
)

from core.domain.exceptions import (
    AuthenticationError,
    BibleVersionNotFound,
    ConflictError,
    DomainError,
    InvalidCredentialsError,
    MediaAccessDeniedError,
    MediaFileNotFoundError,
    MediaFolderNotRuledError,
    MediaPathRejectedError,
    NotFoundError,
    PermissionDeniedError,
    SongsNotFoundError,
    ValidationError,
)
from core.http.exceptions import custom_exception_handler


def _context() -> dict[str, object]:
    return {"request": MagicMock(), "view": MagicMock()}


# ---------------------------------------------------------------------------
# Canonical format helpers
# ---------------------------------------------------------------------------


def _assert_canonical(
    response: Response, expected_code: str, expected_status: int
) -> dict[str, Any]:
    """Assert response matches canonical format and return response data."""
    assert response is not None
    assert response.status_code == expected_status
    assert "error_code" in response.data
    assert "detail" in response.data
    assert response.data["error_code"] == expected_code
    return dict(response.data)


# ---------------------------------------------------------------------------
# Domain exceptions
# ---------------------------------------------------------------------------


class TestDomainExceptions:
    def test_not_found_error(self) -> None:
        exc = NotFoundError("Item not found")
        response = custom_exception_handler(exc, _context())
        _assert_canonical(response, "NOT_FOUND", 404)

    def test_validation_error(self) -> None:
        exc = ValidationError("Invalid input")
        response = custom_exception_handler(exc, _context())
        _assert_canonical(response, "VALIDATION_ERROR", 400)

    def test_conflict_error(self) -> None:
        exc = ConflictError("Already exists")
        response = custom_exception_handler(exc, _context())
        _assert_canonical(response, "CONFLICT", 409)

    def test_authentication_error(self) -> None:
        exc = AuthenticationError("Bad credentials")
        response = custom_exception_handler(exc, _context())
        _assert_canonical(response, "AUTHENTICATION_FAILED", 401)

    def test_generic_domain_error_returns_500(self) -> None:
        exc = DomainError("Something broke")
        response = custom_exception_handler(exc, _context())
        _assert_canonical(response, "DOMAIN_ERROR", 500)

    def test_invalid_credentials_error(self) -> None:
        exc = InvalidCredentialsError()
        response = custom_exception_handler(exc, _context())
        _assert_canonical(response, "AUTHENTICATION_FAILED", 401)

    def test_bible_version_not_found_with_extra_context(self) -> None:
        exc = BibleVersionNotFound("NVI")
        response = custom_exception_handler(exc, _context())
        data = _assert_canonical(response, "NOT_FOUND", 404)
        assert data["version"] == "NVI"

    def test_songs_not_found_with_extra_context(self) -> None:
        exc = SongsNotFoundError([5, 12])
        response = custom_exception_handler(exc, _context())
        data = _assert_canonical(response, "NOT_FOUND", 404)
        assert data["missing_song_ids"] == [5, 12]


# ---------------------------------------------------------------------------
# DRF exceptions
# ---------------------------------------------------------------------------


class TestDRFExceptions:
    def test_not_authenticated(self) -> None:
        response = custom_exception_handler(NotAuthenticated(), _context())
        data = _assert_canonical(response, "NOT_AUTHENTICATED", 401)
        assert data["detail"] == "Faça login para ter acesso."

    def test_authentication_failed(self) -> None:
        response = custom_exception_handler(AuthenticationFailed(), _context())
        data = _assert_canonical(response, "AUTHENTICATION_FAILED", 401)
        assert data["detail"] == "Token inválido ou expirado. Faça login novamente."

    def test_permission_denied_custom_detail(self) -> None:
        exc = PermissionDenied(detail="Disponível apenas para membros.")
        response = custom_exception_handler(exc, _context())
        data = _assert_canonical(response, "PERMISSION_DENIED", 403)
        assert data["detail"] == "Disponível apenas para membros."

    def test_permission_denied_default(self) -> None:
        response = custom_exception_handler(PermissionDenied(), _context())
        _assert_canonical(response, "PERMISSION_DENIED", 403)

    def test_throttled(self) -> None:
        exc = Throttled(wait=30)
        response = custom_exception_handler(exc, _context())
        _assert_canonical(response, "THROTTLED", 429)

    def test_drf_validation_error_dict(self) -> None:
        exc = DRFValidationError({"name": ["Required."], "email": ["Invalid."]})
        response = custom_exception_handler(exc, _context())
        data = _assert_canonical(response, "VALIDATION_ERROR", 400)
        assert "field_errors" in data
        assert data["field_errors"]["name"] == ["Required."]
        assert data["field_errors"]["email"] == ["Invalid."]

    def test_drf_validation_error_list(self) -> None:
        exc = DRFValidationError(["Error one.", "Error two."])
        response = custom_exception_handler(exc, _context())
        data = _assert_canonical(response, "VALIDATION_ERROR", 400)
        assert "field_errors" not in data
        assert "Error one." in data["detail"]

    def test_drf_validation_error_string(self) -> None:
        exc = DRFValidationError("Single error.")
        response = custom_exception_handler(exc, _context())
        data = _assert_canonical(response, "VALIDATION_ERROR", 400)
        # DRF wraps string in a list -> becomes list case
        assert "error_code" in data


# ---------------------------------------------------------------------------
# Unhandled exceptions
# ---------------------------------------------------------------------------


class TestUnhandledExceptions:
    def test_returns_json_500_not_none(self) -> None:
        response = custom_exception_handler(RuntimeError("boom"), _context())
        _assert_canonical(response, "INTERNAL_ERROR", 500)

    def test_debug_mode_includes_message(self, settings: Any) -> None:
        settings.DEBUG = True
        response = custom_exception_handler(RuntimeError("kaboom"), _context())
        data = _assert_canonical(response, "INTERNAL_ERROR", 500)
        assert "kaboom" in data["detail"]

    def test_production_hides_message(self, settings: Any) -> None:
        settings.DEBUG = False
        response = custom_exception_handler(RuntimeError("secret"), _context())
        data = _assert_canonical(response, "INTERNAL_ERROR", 500)
        assert "secret" not in data["detail"]
        assert data["detail"] == "An unexpected error occurred."


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


class TestLogging:
    def test_4xx_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING, logger="core.http.exceptions"):
            custom_exception_handler(NotFoundError("gone"), _context())
        assert "NOT_FOUND" in caplog.text

    def test_5xx_logs_error_with_traceback(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.ERROR, logger="core.http.exceptions"):
            custom_exception_handler(RuntimeError("boom"), _context())
        assert "INTERNAL_ERROR" in caplog.text

    def test_domain_500_logs_error(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.ERROR, logger="core.http.exceptions"):
            custom_exception_handler(DomainError("broken"), _context())
        assert "DOMAIN_ERROR" in caplog.text


# ---------------------------------------------------------------------------
# error_code attribute on all domain exceptions
# ---------------------------------------------------------------------------


class TestErrorCodeAttributes:
    @pytest.mark.parametrize(
        "exc_cls,expected_code",
        [
            (DomainError, "DOMAIN_ERROR"),
            (NotFoundError, "NOT_FOUND"),
            (ValidationError, "VALIDATION_ERROR"),
            (ConflictError, "CONFLICT"),
            (AuthenticationError, "AUTHENTICATION_FAILED"),
            (PermissionDeniedError, "PERMISSION_DENIED"),
        ],
    )
    def test_base_exceptions_have_error_codes(
        self, exc_cls: type[DomainError], expected_code: str
    ) -> None:
        assert exc_cls.error_code == expected_code


# ---------------------------------------------------------------------------
# Permission denied and media exceptions (feature 009)
# ---------------------------------------------------------------------------


class TestPermissionDeniedMapping:
    def test_permission_denied_maps_to_403(self) -> None:
        response = custom_exception_handler(PermissionDeniedError("nope"), _context())
        _assert_canonical(response, "PERMISSION_DENIED", 403)

    def test_media_access_denied_maps_to_403(self) -> None:
        response = custom_exception_handler(MediaAccessDeniedError("members"), _context())
        _assert_canonical(response, "PERMISSION_DENIED", 403)


class TestMediaNotFoundIndistinguishable:
    """Rejected path, unruled folder and missing file must look the same to the caller,
    so probing cannot tell a malformed path from a real miss."""

    @pytest.mark.parametrize(
        "exc_cls", [MediaPathRejectedError, MediaFolderNotRuledError, MediaFileNotFoundError]
    )
    def test_maps_to_404_not_found(self, exc_cls: type[NotFoundError]) -> None:
        response = custom_exception_handler(exc_cls("gallery/x.jpg"), _context())
        _assert_canonical(response, "NOT_FOUND", 404)

    def test_bodies_are_identical_for_the_same_path(self) -> None:
        bodies = [
            custom_exception_handler(exc_cls("gallery/x.jpg"), _context()).data
            for exc_cls in (
                MediaPathRejectedError,
                MediaFolderNotRuledError,
                MediaFileNotFoundError,
            )
        ]
        assert bodies[0] == bodies[1] == bodies[2]
        assert "gallery/x.jpg" in bodies[0]["detail"]
