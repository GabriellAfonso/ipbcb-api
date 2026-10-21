"""Unit tests for the django-axes callbacks in ``core.http.lockout``."""

import json

import pytest
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory, override_settings

from core.http.lockout import (
    ACCOUNT_LOCKED_ERROR_CODE,
    axes_lockout_response,
    axes_lockout_username,
    lockout_cooloff_minutes,
    mark_renders_own_lockout,
)


@pytest.fixture
def post_request() -> HttpRequest:
    return RequestFactory().post("/api/auth/login/", {"username": "  Admin  "})


def test_username_comes_from_credentials_normalised(post_request: HttpRequest) -> None:
    result = axes_lockout_username(post_request, {"username": "  ADMIN "})

    assert result == "admin"


def test_username_falls_back_to_post_when_no_credentials(post_request: HttpRequest) -> None:
    """The admin login form reaches axes through request.POST, not through credentials."""
    assert axes_lockout_username(post_request, None) == "admin"


def test_username_casing_variants_collapse_to_one_key(post_request: HttpRequest) -> None:
    """Regression: without normalisation each casing gets its own budget of failures."""
    keys = {
        axes_lockout_username(post_request, {"username": v}) for v in ("admin", "Admin", "ADMIN")
    }

    assert keys == {"admin"}


def test_username_missing_is_empty_string(post_request: HttpRequest) -> None:
    assert axes_lockout_username(post_request, {"password": "x"}) == ""


def test_lockout_response_is_canonical_429(post_request: HttpRequest) -> None:
    response = axes_lockout_response(post_request)
    body = json.loads(response.content)

    assert response.status_code == 429
    assert body["error_code"] == ACCOUNT_LOCKED_ERROR_CODE
    assert body["cooloff_seconds"] == 30 * 60
    assert "30 minutos" in body["detail"]


@override_settings(AXES_COOLOFF_TIME=None)
def test_lockout_response_without_cooloff_says_contact_an_admin(post_request: HttpRequest) -> None:
    """AXES_COOLOFF_TIME = None means the lockout never expires on its own."""
    body = json.loads(axes_lockout_response(post_request).content)

    assert body["cooloff_seconds"] is None
    assert "administrador" in body["detail"]


def test_marked_response_is_kept(post_request: HttpRequest) -> None:
    """specs/021-user-account R-08: a page that renders its own lockout keeps its HTML."""
    page = mark_renders_own_lockout(HttpResponse("<p>bloqueado</p>", status=429))

    assert axes_lockout_response(post_request, page) is page


def test_unmarked_response_is_replaced(post_request: HttpRequest) -> None:
    """The API and the admin keep getting the canonical JSON."""
    response = axes_lockout_response(post_request, HttpResponse("<p>login</p>"))

    assert json.loads(response.content)["error_code"] == ACCOUNT_LOCKED_ERROR_CODE


def test_cooloff_minutes(post_request: HttpRequest) -> None:
    assert lockout_cooloff_minutes(post_request) == 30


@override_settings(AXES_COOLOFF_TIME=None)
def test_cooloff_minutes_without_cooloff(post_request: HttpRequest) -> None:
    assert lockout_cooloff_minutes(post_request) is None
