"""The public password recovery endpoints
(specs/028-password-recovery/contracts/recovery-api.md)."""

from typing import Final

from dependency_injector.wiring import Provide, inject
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from config.di import Container
from core.http.parsing import require_object_body
from features.accounts.serializers.recovery_serializers import (
    PasswordRecoveryConfirmSerializer,
    PasswordRecoveryRequestSerializer,
)
from features.accounts.services.password_recovery_service import PasswordRecoveryService

# The same whatever happened: this text is the whole answer to "is there an account?".
_REQUEST_ANSWER: Final = "Se houver conta com esse e-mail, enviamos um código."


class PasswordRecoveryRequestAPI(APIView):
    """POST: ask for codes. Reads no token: an expired one must not break a signed-out flow."""

    authentication_classes: list[type] = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "recovery_request"

    def check_throttles(self, request: Request) -> None:
        """Note a spent client budget instead of answering 429: the public response stays the
        same when any limit is hit (research R-05). A list, not a generator: every throttle must
        count the request.

        >>> view.check_throttles(request)
        """
        answers = [throttle.allow_request(request, self) for throttle in self.get_throttles()]
        self._client_over_limit = not all(answers)

    @extend_schema(request=PasswordRecoveryRequestSerializer, responses={200: None})
    @inject
    def post(
        self,
        request: Request,
        password_recovery_service: PasswordRecoveryService = Provide[
            Container.password_recovery_service
        ],
    ) -> Response:
        serializer = PasswordRecoveryRequestSerializer(data=require_object_body(request.data))
        serializer.is_valid(raise_exception=True)
        if not self._client_over_limit:
            password_recovery_service.request_codes(serializer.create_dto())
        return Response({"detail": _REQUEST_ANSWER}, status=status.HTTP_200_OK)


class PasswordRecoveryConfirmAPI(APIView):
    """POST: set the new password with a code. No tokens in the answer: the app returns to login,
    which also confirms the person knows the new password."""

    authentication_classes: list[type] = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(request=PasswordRecoveryConfirmSerializer, responses={204: None})
    @inject
    def post(
        self,
        request: Request,
        password_recovery_service: PasswordRecoveryService = Provide[
            Container.password_recovery_service
        ],
    ) -> Response:
        serializer = PasswordRecoveryConfirmSerializer(data=require_object_body(request.data))
        serializer.is_valid(raise_exception=True)
        password_recovery_service.confirm(serializer.create_dto())
        return Response(status=status.HTTP_204_NO_CONTENT)
