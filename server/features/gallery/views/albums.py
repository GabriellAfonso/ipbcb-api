from dependency_injector.wiring import Provide, inject
from rest_framework import status
from rest_framework.parsers import JSONParser
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from config.di import Container
from core.http.parsing import require_object_body
from features.gallery.dtos.gallery_dtos import AlbumChanges, AlbumCreate, SiblingOrder
from features.gallery.serializers.album_serializers import (
    AlbumCreateSerializer,
    AlbumOrderSerializer,
    AlbumSerializer,
    AlbumUpdateSerializer,
)
from features.gallery.services.album_service import AlbumService
from features.gallery.views.gallery import GALLERY_WRITE
from features.gallery.views.permissions import member_read_gallery_write_permissions


class AlbumListCreateAPIView(APIView):
    """``GET`` every album, flat, in tree order (members); ``POST`` creates one (``manage``)."""

    serializer_class = AlbumSerializer
    parser_classes = [JSONParser]

    def get_permissions(self) -> list[BasePermission]:
        return member_read_gallery_write_permissions(self.request.method or "GET")

    @inject
    def get(
        self,
        request: Request,
        album_service: AlbumService = Provide[Container.album_service],
    ) -> Response:
        albums = album_service.list_albums()
        return Response(AlbumSerializer(albums, many=True, context={"request": request}).data)

    @inject
    def post(
        self,
        request: Request,
        album_service: AlbumService = Provide[Container.album_service],
    ) -> Response:
        serializer = AlbumCreateSerializer(data=require_object_body(request.data))
        serializer.is_valid(raise_exception=True)
        album = album_service.create(AlbumCreate(**serializer.validated_data))
        body = AlbumSerializer(album, context={"request": request}).data
        return Response(body, status=status.HTTP_201_CREATED)


class AlbumDetailAPIView(APIView):
    """``PATCH`` renames, moves (``parent_id``; ``null`` = root) or edits an album."""

    serializer_class = AlbumUpdateSerializer
    permission_classes = GALLERY_WRITE
    parser_classes = [JSONParser]

    @inject
    def patch(
        self,
        request: Request,
        album_id: int,
        album_service: AlbumService = Provide[Container.album_service],
    ) -> Response:
        serializer = AlbumUpdateSerializer(data=require_object_body(request.data))
        serializer.is_valid(raise_exception=True)
        album = album_service.update(album_id, AlbumChanges(**serializer.validated_data))
        return Response(AlbumSerializer(album, context={"request": request}).data)


class AlbumOrderAPIView(APIView):
    """``PUT`` the full new order of one set of sibling albums."""

    serializer_class = AlbumOrderSerializer
    permission_classes = GALLERY_WRITE
    parser_classes = [JSONParser]

    @inject
    def put(
        self,
        request: Request,
        album_service: AlbumService = Provide[Container.album_service],
    ) -> Response:
        serializer = AlbumOrderSerializer(data=require_object_body(request.data))
        serializer.is_valid(raise_exception=True)
        album_service.reorder(SiblingOrder(**serializer.validated_data))
        return Response(status=status.HTTP_204_NO_CONTENT)
