"""The signed-in recovery e-mail endpoints
(specs/028-password-recovery/contracts/recovery-api.md)."""

from typing import cast

from dependency_injector.wiring import Provide, inject
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
from features.accounts.serializers.recovery_serializers import (
    RecoveryEmailChangeSerializer,
    RecoveryEmailConfirmSerializer,
    RecoveryEmailStateSerializer,
)
from features.accounts.services.login_service import LoginService
from features.accounts.services.recovery_email_service import RecoveryEmailService
from features.accounts.views.account import password_check_for


class RecoveryEmailAPIView(APIView):
    """POST: set or change the address, confirmed by the current password."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(
        request=RecoveryEmailChangeSerializer, responses={200: RecoveryEmailStateSerializer}
    )
    @inject
    def post(
        self,
        request: Request,
        recovery_email_service: RecoveryEmailService = Provide[Container.recovery_email_service],
        login_service: LoginService = Provide[Container.login_service],
    ) -> Response:
        user = cast(User, request.user)
        serializer = RecoveryEmailChangeSerializer(data=require_object_body(request.data))
        serializer.is_valid(raise_exception=True)
        profile = recovery_email_service.change_email(
            user, serializer.create_dto(), password_check_for(login_service, user, request)
        )
        return Response(RecoveryEmailStateSerializer(profile).data, status=status.HTTP_200_OK)


class RecoveryEmailSendCodeAPIView(APIView):
    """POST: send a confirmation code to the current address."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(request=None, responses={204: None})
    @inject
    def post(
        self,
        request: Request,
        recovery_email_service: RecoveryEmailService = Provide[Container.recovery_email_service],
    ) -> Response:
        recovery_email_service.send_confirmation_code(cast(User, request.user))
        return Response(status=status.HTTP_204_NO_CONTENT)


class RecoveryEmailConfirmAPIView(APIView):
    """POST: confirm the current address with a code."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(
        request=RecoveryEmailConfirmSerializer, responses={200: RecoveryEmailStateSerializer}
    )
    @inject
    def post(
        self,
        request: Request,
        recovery_email_service: RecoveryEmailService = Provide[Container.recovery_email_service],
    ) -> Response:
        serializer = RecoveryEmailConfirmSerializer(data=require_object_body(request.data))
        serializer.is_valid(raise_exception=True)
        profile = recovery_email_service.confirm_email(
            cast(User, request.user), serializer.validated_data["code"]
        )
        return Response(RecoveryEmailStateSerializer(profile).data, status=status.HTTP_200_OK)
