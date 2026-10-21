"""The account-deletion web page Google Play requires beside the in-app option
(specs/021-user-account FR-016–FR-019, research R-08/R-09).

A plain Django view, not a DRF ``APIView``: Django's CSRF middleware protects it natively,
whereas ``APIView`` is CSRF-exempt unless session authentication runs.
"""

from typing import Any, cast

from dependency_injector.wiring import inject, Provide
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from rest_framework.request import Request
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from config.di import Container
from core.application.dtos.auth_dtos import LoginDTO
from core.domain.exceptions import (
    AccountDeletionBlockedError,
    ConfirmationMethodError,
    GoogleAccountMismatchError,
    InvalidCredentialsError,
    InvalidGoogleConfirmationError,
)
from core.http.lockout import lockout_cooloff_minutes, mark_renders_own_lockout
from features.accounts.serializers.web_serializers import (
    WebGoogleDeletionSerializer,
    WebPasswordDeletionSerializer,
    first_error,
)
from features.accounts.services.account_deletion_service import AccountDeletionService
from features.accounts.services.login_service import LoginService

TEMPLATE = "accounts/account_deletion.html"
INVALID_CREDENTIALS_MESSAGE = "Usuário ou senha inválidos."
# The page's own wording where the API's message assumes someone already signed in.
_GOOGLE_PAGE_MESSAGES: dict[type[Exception], str] = {
    GoogleAccountMismatchError: "Nenhuma conta do app usa esta conta Google.",
    ConfirmationMethodError: "Esta conta tem senha; entre com usuário e senha.",
}
_GOOGLE_PAGE_ERRORS = (
    GoogleAccountMismatchError,
    ConfirmationMethodError,
    InvalidGoogleConfirmationError,
    AccountDeletionBlockedError,
)


class AccountDeletionPageThrottle(SimpleRateThrottle):
    """The auth endpoints' ``login`` budget, per client address. DRF throttles never run on a
    plain view, so the page calls this one itself. ``get_ident`` honours ``NUM_PROXIES`` like
    every other throttle (constitution: Client IP)."""

    scope = "login"

    def get_cache_key(self, request: Any, view: Any) -> str:
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}

    def allows(self, request: HttpRequest) -> bool:
        """``allow_request`` is typed for DRF's ``Request``, but this throttle only reads
        ``request.META`` (through ``get_ident``), which a Django request has too.

        >>> AccountDeletionPageThrottle().allows(request)
        True
        """
        return self.allow_request(cast(Request, request), cast(APIView, None))


def _page(request: HttpRequest, state: str, error: str = "", status: int = 200) -> HttpResponse:
    """Render the page in one of its states: ``form``, ``done``, ``locked``, ``throttled``."""
    context = {
        "state": state,
        "error": error,
        "google_client_id": settings.GOOGLE_CLIENT_ID,
        "cooloff_minutes": lockout_cooloff_minutes(request) if state == "locked" else None,
    }
    response = render(request, TEMPLATE, context, status=status)
    # SecurityMiddleware only sets these when absent. The Google popup must be able to talk
    # back to the page, and the button refuses to render without the origin in the referrer.
    response["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
    response["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@method_decorator(never_cache, name="dispatch")
class AccountDeletionPageView(View):
    """GET shows the form; POST deletes with ``method=password`` or ``method=google``."""

    def get(self, request: HttpRequest) -> HttpResponse:
        return _page(request, "form")

    @inject
    def post(
        self,
        request: HttpRequest,
        deletion_service: AccountDeletionService = Provide[Container.account_deletion_service],
        login_service: LoginService = Provide[Container.login_service],
    ) -> HttpResponse:
        if not AccountDeletionPageThrottle().allows(request):
            return _page(request, "throttled", status=429)
        if request.POST.get("method") == "google":
            return _delete_by_google(request, deletion_service)
        return _delete_by_password(request, deletion_service, login_service)


def _delete_by_password(
    request: HttpRequest, deletion_service: AccountDeletionService, login_service: LoginService
) -> HttpResponse:
    serializer = WebPasswordDeletionSerializer(data=request.POST)
    if not serializer.is_valid():
        return _page(request, "form", first_error(serializer))
    credentials = LoginDTO(
        username=serializer.validated_data["username"],
        password=serializer.validated_data["password"],
    )
    try:
        user = login_service.authenticate_credentials(credentials, request)
    except InvalidCredentialsError:
        return _failed_sign_in(request)
    try:
        deletion_service.delete_authenticated(user)
    except AccountDeletionBlockedError as exc:
        return _page(request, "form", str(exc))
    return _page(request, "done")


def _failed_sign_in(request: HttpRequest) -> HttpResponse:
    # Generic on purpose: the page must not tell whether the username exists (FR-017).
    if getattr(request, "axes_locked_out", False):
        return mark_renders_own_lockout(_page(request, "locked", status=429))
    return _page(request, "form", INVALID_CREDENTIALS_MESSAGE)


def _delete_by_google(
    request: HttpRequest, deletion_service: AccountDeletionService
) -> HttpResponse:
    serializer = WebGoogleDeletionSerializer(data=request.POST)
    if not serializer.is_valid():
        return _page(request, "form", first_error(serializer))
    try:
        deletion_service.delete_by_google(serializer.validated_data["credential"])
    except _GOOGLE_PAGE_ERRORS as exc:
        return _page(request, "form", _google_page_message(exc))
    return _page(request, "done")


def _google_page_message(exc: Exception) -> str:
    """By ``isinstance``, never ``type(exc)`` (constitution: Error shape).

    >>> _google_page_message(GoogleAccountMismatchError())
    'Nenhuma conta do app usa esta conta Google.'
    """
    for cls, message in _GOOGLE_PAGE_MESSAGES.items():
        if isinstance(exc, cls):
            return message
    return str(exc)
