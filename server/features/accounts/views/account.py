"""Account self-service: password change and account deletion
(specs/021-user-account/contracts/account-api.md)."""

from typing import cast

from dependency_injector.wiring import inject, Provide
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from config.di import Container
from core.http.parsing import require_object_body
from features.accounts.models.user import User
from features.accounts.serializers.serializers import (
    AccountDeletionSerializer,
    PasswordChangeSerializer,
    TokenSerializer,
)
from features.accounts.services.account_deletion_service import AccountDeletionService
from features.accounts.services.login_service import LoginService
from features.accounts.services.password_change_service import PasswordChangeService
from features.accounts.services.password_check import PasswordCheck


def _password_check(login_service: LoginService, user: User, request: Request) -> PasswordCheck:
    """The lockout-guarded check the services call. The underlying ``HttpRequest``, not DRF's
    wrapper: ``AxesMiddleware`` only ever sees the Django one (same reason as ``LoginAPI``).

    >>> _password_check(login_service, user, request)("secret1")
    """
    django_request = request._request
    return lambda raw: login_service.verify_password(user, raw, django_request)


class PasswordChangeAPIView(APIView):
    """POST: change the password. The answer's pair replaces the caller's tokens: the access
    token used for this request stops working at once."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(request=PasswordChangeSerializer, responses={200: TokenSerializer})
    @inject
    def post(
        self,
        request: Request,
        password_change_service: PasswordChangeService = Provide[Container.password_change_service],
        login_service: LoginService = Provide[Container.login_service],
    ) -> Response:
        user = cast(User, request.user)
        serializer = PasswordChangeSerializer(data=require_object_body(request.data))
        serializer.is_valid(raise_exception=True)
        tokens = password_change_service.change_password(
            user, serializer.create_dto(), _password_check(login_service, user, request)
        )
        return Response(tokens.model_dump(), status=status.HTTP_200_OK)


class AccountDeletionAPIView(APIView):
    """POST, not DELETE: the confirmation secret travels in the body, never in a URL."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(request=AccountDeletionSerializer, responses={204: None})
    @inject
    def post(
        self,
        request: Request,
        account_deletion_service: AccountDeletionService = Provide[
            Container.account_deletion_service
        ],
        login_service: LoginService = Provide[Container.login_service],
    ) -> Response:
        user = cast(User, request.user)
        serializer = AccountDeletionSerializer(data=require_object_body(request.data))
        serializer.is_valid(raise_exception=True)
        account_deletion_service.delete_confirmed(
            user, serializer.create_dto(), _password_check(login_service, user, request)
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
