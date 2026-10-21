"""Project-owned callbacks that django-axes calls into.

The library is configured through two hooks (``AXES_USERNAME_CALLABLE`` and
``AXES_LOCKOUT_CALLABLE``) so the parts this project cares about — which key an attempt is
counted under, and what a locked-out client receives — stay here rather than in the
library's defaults. Both defaults are wrong for this deployment; see
``specs/008-login-brute-force-lockout/plan.md`` D-4 and D-5.
"""

from __future__ import annotations

from typing import Any, Final, Optional

# axes.conf, not django.conf: reading it is what fills in the library's own defaults, and
# AXES_USERNAME_FORM_FIELD and AXES_HTTP_RESPONSE_CODE below are defaults this project
# never overrides. Through django.conf they simply would not exist.
from axes.conf import settings
from axes.helpers import get_cool_off
from django.http import HttpRequest, HttpResponse, JsonResponse

from core.application.username import normalize_username
from core.http.exceptions import build_canonical_error

ACCOUNT_LOCKED_ERROR_CODE: Final = "ACCOUNT_LOCKED"

# Set on a response that already tells a locked-out person, in its own format, to wait.
_RENDERS_OWN_LOCKOUT_ATTR: Final = "renders_own_lockout"

# User-facing, so Portuguese — it reaches the Android app and the admin login page.
_PERMANENT_LOCKOUT_DETAIL: Final = (
    "Muitas tentativas de login. Peça a um administrador para liberar o acesso."
)


def axes_lockout_username(
    request: HttpRequest, credentials: Optional[dict[str, Any]] = None
) -> str:
    """Return the username django-axes should count this attempt against.

    Normalised, because the two entry points disagree otherwise: ``LoginDTO`` lowercases
    and the admin login form does not, so "admin", "Admin" and "ADMIN" would each get
    their own budget of failures.

    >>> axes_lockout_username(request, {"username": " Admin "})
    'admin'
    """
    return normalize_username(_raw_username(request, credentials))


def _raw_username(request: HttpRequest, credentials: Optional[dict[str, Any]]) -> str:
    field = str(settings.AXES_USERNAME_FORM_FIELD)
    if credentials:
        return str(credentials.get(field) or "")
    # DRF requests expose the parsed body as ``.data``; the admin login form uses ``.POST``.
    submitted: Any = getattr(request, "data", None)
    if submitted is None:
        submitted = getattr(request, "POST", {})
    return str(submitted.get(field) or "")


def axes_lockout_response(
    request: HttpRequest,
    original_response: Optional[HttpResponse] = None,
    credentials: Optional[dict[str, Any]] = None,
) -> HttpResponse:
    """Return the lockout response in this API's canonical error shape.

    The library's own default renders HTML, and only emits JSON when the request carries
    ``X-Requested-With: XMLHttpRequest`` — which the Android app, the single client, does
    not send. ``cooloff_seconds`` is included so the app can count down instead of
    hardcoding the window.

    A response marked with ``mark_renders_own_lockout`` is returned unchanged: an HTML page
    answering with JSON would show raw text to the person locked out.

    >>> axes_lockout_response(request).status_code
    429
    """
    if original_response is not None and getattr(
        original_response, _RENDERS_OWN_LOCKOUT_ATTR, False
    ):
        return original_response
    cool_off = get_cool_off(request)
    seconds = int(cool_off.total_seconds()) if cool_off else None
    body = build_canonical_error(
        ACCOUNT_LOCKED_ERROR_CODE,
        _lockout_detail(seconds),
        cooloff_seconds=seconds,
    )
    status: int = settings.AXES_HTTP_RESPONSE_CODE
    return JsonResponse(body, status=status)


def mark_renders_own_lockout(response: HttpResponse) -> HttpResponse:
    """Keep ``response`` when django-axes would replace it with the JSON lockout. For a page
    that renders the lockout message itself (the account-deletion page,
    specs/021-user-account R-08); the API and the admin keep the JSON.

    >>> mark_renders_own_lockout(render(request, "page.html", status=429)).status_code
    429
    """
    setattr(response, _RENDERS_OWN_LOCKOUT_ATTR, True)
    return response


def lockout_cooloff_minutes(request: HttpRequest) -> Optional[int]:
    """Minutes left of the lockout window, for a page that words the wait itself.

    >>> lockout_cooloff_minutes(request)
    30
    """
    cool_off = get_cool_off(request)
    if cool_off is None:
        return None
    return max(1, round(float(cool_off.total_seconds()) / 60))


def _lockout_detail(cooloff_seconds: Optional[int]) -> str:
    """Describe the wait. ``AXES_COOLOFF_TIME = None`` means the lockout never expires."""
    if cooloff_seconds is None:
        return _PERMANENT_LOCKOUT_DETAIL
    minutes = max(1, round(cooloff_seconds / 60))
    return f"Muitas tentativas de login. Tente novamente em {minutes} minutos."
