"""Device push tokens of the caller (specs/017-sunday-setlist-push, contracts/me-api.md).

POST for both: the token is long and is a credential to the phone, so it never goes in a URL,
where access logs would keep it.
"""

from typing import cast
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from config.di import Container
from core.application.device_token_service import DeviceTokenService
from core.http.parsing import require_object_body


class DeviceTokenRegisterAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @inject
    def post(
        self,
        request: Request,
        device_token_service: DeviceTokenService = Provide[Container.device_token_service],
    ) -> Response:
        body = require_object_body(request.data)
        device_token_service.register(cast(UUID, request.user.pk), body.get("token"))
        return Response(status=status.HTTP_204_NO_CONTENT)


class DeviceTokenUnregisterAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @inject
    def post(
        self,
        request: Request,
        device_token_service: DeviceTokenService = Provide[Container.device_token_service],
    ) -> Response:
        body = require_object_body(request.data)
        device_token_service.unregister(cast(UUID, request.user.pk), body.get("token"))
        return Response(status=status.HTTP_204_NO_CONTENT)
