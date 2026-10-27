"""Reading progress endpoints (specs/025-bible-videos US4). Any signed-in user, no scope; each
user reads and writes only their own marks."""

from typing import cast
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
from core.http.utils import _not_modified_or_response
from features.bible.progress_dtos import ProgressSyncDTO
from features.bible.serializers import (
    BibleProgressStateSerializer,
    BibleProgressSyncResultSerializer,
    BibleProgressSyncSerializer,
)
from features.bible.services.progress_service import BibleProgressService


class BibleProgressView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(operation_id="bible_progress_retrieve", responses=BibleProgressStateSerializer)
    @inject
    def get(
        self,
        request: Request,
        progress_service: BibleProgressService = Provide[Container.bible_progress_service],
    ) -> Response:
        state = progress_service.state(cast(UUID, request.user.pk))
        return _not_modified_or_response(request, state.model_dump(mode="json"), private=True)


class BibleProgressSyncView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="bible_progress_sync",
        request=BibleProgressSyncSerializer,
        responses=BibleProgressSyncResultSerializer,
    )
    @inject
    def post(
        self,
        request: Request,
        progress_service: BibleProgressService = Provide[Container.bible_progress_service],
    ) -> Response:
        dto = ProgressSyncDTO.model_validate(require_object_body(request.data))
        result = progress_service.sync(cast(UUID, request.user.pk), dto.changes)
        return Response(result.model_dump(mode="json"), status=status.HTTP_200_OK)
