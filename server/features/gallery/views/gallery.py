from typing import Any

from dependency_injector.wiring import Provide, inject
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from config.di import Container
from core.domain.access import Scope
from core.domain.exceptions import ValidationError
from core.http.parsing import require_int, require_object_body
from core.http.permissions import IsMemberUser, scope_permission
from features.gallery.dtos.gallery_dtos import PhotoChanges, UploadResult
from features.gallery.serializers.serializers import (
    PhotoOrderSerializer,
    PhotoSerializer,
    PhotoUpdateSerializer,
    RejectedFileSerializer,
)
from features.gallery.services.gallery_service import GalleryService
from features.gallery.views.permissions import member_read_gallery_write_permissions

GALLERY_WRITE: list[type[BasePermission]] = [IsAuthenticated, scope_permission(Scope.GALLERY)]


def _upload_body(request: Request, result: UploadResult) -> dict[str, Any]:
    context = {"request": request}
    return {
        "accepted": PhotoSerializer(result.accepted, many=True, context=context).data,
        "rejected": RejectedFileSerializer(result.rejected, many=True).data,
    }


class PhotoListAPIView(APIView):
    """``GET`` every photo (members); ``POST`` uploads into an album (``manage`` on gallery).

    Upload answers 201 when every file was accepted and 207 when some were refused; when none
    was, the service raises and the canonical 400 carries ``rejected``
    (specs/013-gallery-write-api/contracts/gallery-api.md).
    """

    serializer_class = PhotoSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_permissions(self) -> list[BasePermission]:
        return member_read_gallery_write_permissions(self.request.method or "GET")

    @inject
    def get(
        self,
        request: Request,
        gallery_service: GalleryService = Provide[Container.gallery_service],
    ) -> Response:
        photos = gallery_service.list_all_photos()
        serializer = PhotoSerializer(photos, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @inject
    def post(
        self,
        request: Request,
        gallery_service: GalleryService = Provide[Container.gallery_service],
    ) -> Response:
        album_id = require_int(request.data.get("album_id"), "album_id")
        files = request.FILES.getlist("image")
        if not files:
            raise ValidationError("Envie ao menos uma imagem no campo 'image'.")
        result = gallery_service.upload_photos(album_id, files, request.user.pk)
        code = status.HTTP_207_MULTI_STATUS if result.rejected else status.HTTP_201_CREATED
        return Response(_upload_body(request, result), status=code)


class AlbumPhotoListAPIView(APIView):
    """Photos directly in one album; 404 for an unknown album."""

    serializer_class = PhotoSerializer
    permission_classes = [IsMemberUser]

    @inject
    def get(
        self,
        request: Request,
        album_id: int,
        gallery_service: GalleryService = Provide[Container.gallery_service],
    ) -> Response:
        photos = gallery_service.list_photos_by_album(album_id)
        serializer = PhotoSerializer(photos, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class PhotoDetailAPIView(APIView):
    """``PATCH`` a photo's metadata or move it to another album; never its image."""

    serializer_class = PhotoUpdateSerializer
    permission_classes = GALLERY_WRITE
    parser_classes = [JSONParser]

    @inject
    def patch(
        self,
        request: Request,
        photo_id: int,
        gallery_service: GalleryService = Provide[Container.gallery_service],
    ) -> Response:
        serializer = PhotoUpdateSerializer(data=require_object_body(request.data))
        serializer.is_valid(raise_exception=True)
        photo = gallery_service.update_photo(photo_id, PhotoChanges(**serializer.validated_data))
        return Response(PhotoSerializer(photo, context={"request": request}).data)


class AlbumPhotoOrderAPIView(APIView):
    """``PUT`` the full new order of an album's photos."""

    serializer_class = PhotoOrderSerializer
    permission_classes = GALLERY_WRITE
    parser_classes = [JSONParser]

    @inject
    def put(
        self,
        request: Request,
        album_id: int,
        gallery_service: GalleryService = Provide[Container.gallery_service],
    ) -> Response:
        serializer = PhotoOrderSerializer(data=require_object_body(request.data))
        serializer.is_valid(raise_exception=True)
        gallery_service.reorder_photos(album_id, serializer.validated_data["ids"])
        return Response(status=status.HTTP_204_NO_CONTENT)
