"""Bible videos endpoints (specs/025-bible-videos).

Access: the list is public, like the Bible text. Writes need scope ``bible_videos`` by method —
POST/PUT manage, DELETE owner (specs/012-feature-role-permissions); Admin and Liderança hold
``owner``, Mídia nothing.
"""

from typing import cast
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from config.di import Container
from core.domain.access import Scope
from core.http.parsing import optional_single_value, require_object_body
from core.http.permissions import scope_permission
from core.http.utils import _not_modified_or_response
from features.bible.serializers import (
    BibleVideoCreateSerializer,
    BibleVideoOrderSerializer,
    BibleVideoPlacesSerializer,
    BibleVideoSerializer,
)
from features.bible.services.video_service import BibleVideoService
from features.bible.video_dtos import (
    BiblePlaceQueryDTO,
    BibleVideoCreateDTO,
    BibleVideoDTO,
    BibleVideoOrderDTO,
    BibleVideoPlacesDTO,
)

_BibleVideosPermission = scope_permission(Scope.BIBLE_VIDEOS)

_PLACE_PARAMETERS = [
    OpenApiParameter(name="book", type=str, required=True),
    OpenApiParameter(name="chapter", type=int, required=False, description="Absent = whole book"),
]


def _manager_permissions() -> list[BasePermission]:
    return [IsAuthenticated(), _BibleVideosPermission()]


def _video_or_gone(video: BibleVideoDTO | None) -> Response:
    """200 with the video, or 204 when the change deleted it (its last place went away)."""
    if video is None:
        return Response(status=status.HTTP_204_NO_CONTENT)
    return Response(video.model_dump(mode="json"), status=status.HTTP_200_OK)


def _place_query(request: Request) -> BiblePlaceQueryDTO:
    """``?book=Gn&chapter=1`` — query parameters, since some clients drop DELETE bodies."""
    present: dict[str, str] = {}
    for key in ("book", "chapter"):
        value = optional_single_value(request.query_params.getlist(key), key)
        if value is not None:
            present[key] = value
    return BiblePlaceQueryDTO.model_validate(present)


class BibleVideoListView(APIView):
    def get_permissions(self) -> list[BasePermission]:
        if self.request.method == "GET":
            return [AllowAny()]
        return _manager_permissions()

    @extend_schema(operation_id="bible_videos_list", responses=BibleVideoSerializer(many=True))
    @inject
    def get(
        self,
        request: Request,
        video_service: BibleVideoService = Provide[Container.bible_video_service],
    ) -> Response:
        body = [video.model_dump(mode="json") for video in video_service.list_videos()]
        return _not_modified_or_response(request, body)

    @extend_schema(
        operation_id="bible_videos_create",
        request=BibleVideoCreateSerializer,
        responses={201: BibleVideoSerializer},
    )
    @inject
    def post(
        self,
        request: Request,
        video_service: BibleVideoService = Provide[Container.bible_video_service],
    ) -> Response:
        dto = BibleVideoCreateDTO.model_validate(require_object_body(request.data))
        video = video_service.create(dto, cast(UUID, request.user.pk))
        return Response(video.model_dump(mode="json"), status=status.HTTP_201_CREATED)


class BibleVideoDetailView(APIView):
    permission_classes = [IsAuthenticated, _BibleVideosPermission]

    @extend_schema(operation_id="bible_videos_destroy", responses={204: None})
    @inject
    def delete(
        self,
        request: Request,
        video_id: int,
        video_service: BibleVideoService = Provide[Container.bible_video_service],
    ) -> Response:
        video_service.delete(video_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class BibleVideoPlacesView(APIView):
    permission_classes = [IsAuthenticated, _BibleVideosPermission]

    @extend_schema(
        operation_id="bible_videos_places_update",
        request=BibleVideoPlacesSerializer,
        responses={200: BibleVideoSerializer, 204: None},
    )
    @inject
    def put(
        self,
        request: Request,
        video_id: int,
        video_service: BibleVideoService = Provide[Container.bible_video_service],
    ) -> Response:
        dto = BibleVideoPlacesDTO.model_validate(require_object_body(request.data))
        return _video_or_gone(video_service.replace_places(video_id, dto.places))

    @extend_schema(
        operation_id="bible_videos_places_destroy",
        parameters=_PLACE_PARAMETERS,
        responses={200: BibleVideoSerializer, 204: None},
    )
    @inject
    def delete(
        self,
        request: Request,
        video_id: int,
        video_service: BibleVideoService = Provide[Container.bible_video_service],
    ) -> Response:
        place = _place_query(request)
        return _video_or_gone(video_service.remove_place(video_id, place.book, place.chapter))


class BibleVideoOrderView(APIView):
    permission_classes = [IsAuthenticated, _BibleVideosPermission]

    @extend_schema(
        operation_id="bible_videos_order_update",
        request=BibleVideoOrderSerializer,
        responses={204: None},
    )
    @inject
    def put(
        self,
        request: Request,
        video_service: BibleVideoService = Provide[Container.bible_video_service],
    ) -> Response:
        dto = BibleVideoOrderDTO.model_validate(require_object_body(request.data))
        video_service.set_order(dto)
        return Response(status=status.HTTP_204_NO_CONTENT)
