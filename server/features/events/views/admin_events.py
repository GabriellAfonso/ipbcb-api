"""Management endpoints for events (specs/020-church-events).

Access: scope ``events``, level by method — GET view, POST/PATCH manage, DELETE owner
(specs/012-feature-role-permissions). Admin, Liderança and Mídia all hold ``owner``. Writes are
multipart because they carry the image.
"""

from typing import IO, cast
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from config.di import Container
from core.domain.access import Scope
from core.http.parsing import optional_single_value
from core.http.permissions import scope_permission
from core.http.utils import _not_modified_or_response
from features.events.dtos import EventCreateDTO, EventPatchDTO
from features.events.serializers import (
    EventManagementListSerializer,
    EventRecordSerializer,
    EventWriteSchemaSerializer,
    EventWriteSerializer,
)
from features.events.services.event_service import EventService
from features.events.services.event_write_service import EventWriteService
from features.events.views.responses import record_body, record_list_body

_EventsPermission = scope_permission(Scope.EVENTS)

_STATUS_PARAMETER = OpenApiParameter(
    name="status", enum=["active", "past", "all"], default="all", required=False
)


def _uploaded_image(request: Request) -> IO[bytes] | None:
    """The file sent in the ``image`` part, handed over whole: the service validates it."""
    return cast(IO[bytes] | None, request.FILES.get("image"))


def _validated_fields(request: Request, partial: bool) -> dict[str, object]:
    serializer = EventWriteSerializer(data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    return dict(serializer.validated_data)


class AdminEventListAPIView(APIView):
    permission_classes = [IsAuthenticated, _EventsPermission]
    parser_classes = [MultiPartParser, FormParser]

    # A plain APIView has no list serializer, so drf-spectacular names this GET "_retrieve" and
    # collides with the detail view's (drf_spectacular.W001).
    @extend_schema(
        operation_id="api_admin_events_list",
        parameters=[_STATUS_PARAMETER],
        responses=EventManagementListSerializer,
    )
    @inject
    def get(
        self,
        request: Request,
        event_service: EventService = Provide[Container.event_service],
    ) -> Response:
        status_raw = optional_single_value(request.query_params.getlist("status"), "status")
        records = event_service.list_for_management(status_raw)
        body = record_list_body(request, event_service, records)
        return _not_modified_or_response(request, body, private=True)

    @extend_schema(request=EventWriteSchemaSerializer, responses={201: EventRecordSerializer})
    @inject
    def post(
        self,
        request: Request,
        event_service: EventService = Provide[Container.event_service],
        write_service: EventWriteService = Provide[Container.event_write_service],
    ) -> Response:
        dto = EventCreateDTO.model_validate(_validated_fields(request, partial=False))
        creator_id = cast(UUID, request.user.pk)
        record = write_service.create_event(dto, _uploaded_image(request), creator_id)
        body = record_body(request, event_service, record)
        return Response(body, status=status.HTTP_201_CREATED)


class AdminEventDetailAPIView(APIView):
    permission_classes = [IsAuthenticated, _EventsPermission]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(operation_id="api_admin_events_retrieve", responses=EventRecordSerializer)
    @inject
    def get(
        self,
        request: Request,
        event_id: int,
        event_service: EventService = Provide[Container.event_service],
    ) -> Response:
        record = event_service.get_for_management(event_id)
        body = record_body(request, event_service, record)
        return _not_modified_or_response(request, body, private=True)

    @extend_schema(request=EventWriteSchemaSerializer, responses=EventRecordSerializer)
    @inject
    def patch(
        self,
        request: Request,
        event_id: int,
        event_service: EventService = Provide[Container.event_service],
        write_service: EventWriteService = Provide[Container.event_write_service],
    ) -> Response:
        # Only the keys the app sent are in validated_data, so model_fields_set tells
        # "leave alone" from "clear".
        dto = EventPatchDTO.model_validate(_validated_fields(request, partial=True))
        editor_id = cast(UUID, request.user.pk)
        record = write_service.update_event(event_id, dto, _uploaded_image(request), editor_id)
        return Response(record_body(request, event_service, record), status=status.HTTP_200_OK)

    @extend_schema(responses={204: None})
    @inject
    def delete(
        self,
        request: Request,
        event_id: int,
        write_service: EventWriteService = Provide[Container.event_write_service],
    ) -> Response:
        write_service.delete_event(event_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
