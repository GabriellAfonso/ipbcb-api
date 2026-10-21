"""An account asks the leadership for member access or a roll correction
(specs/022-access-requests contracts/access-api.md)."""

from typing import Any, cast
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from config.di import Container
from core.http.parsing import require_object_body
from features.accounts.dtos import AccessRequestRecordDTO
from features.accounts.serializers.access_request_serializers import (
    AccessRequestCreateSerializer,
    AccessRequestRecordSerializer,
)
from features.accounts.services.access_request_service import AccessRequestService


def request_body(record: AccessRequestRecordDTO) -> dict[str, Any]:
    """The request resource, without ``user_id`` (the caller knows who they are).

    >>> request_body(record)["status"]
    'pending'
    """
    return dict(AccessRequestRecordSerializer(record.model_dump()).data)


class MeAccessRequestAPIView(APIView):
    """POST: create a request. The 24-hour limit is a domain rule (429), not a DRF throttle."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=AccessRequestCreateSerializer, responses={201: AccessRequestRecordSerializer}
    )
    @inject
    def post(
        self,
        request: Request,
        access_request_service: AccessRequestService = Provide[Container.access_request_service],
    ) -> Response:
        serializer = AccessRequestCreateSerializer(data=require_object_body(request.data))
        serializer.is_valid(raise_exception=True)
        user_id = cast(UUID, request.user.pk)
        record = access_request_service.create_request(user_id, serializer.create_dto())
        return Response(request_body(record), status=status.HTTP_201_CREATED)
