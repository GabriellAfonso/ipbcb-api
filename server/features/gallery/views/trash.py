from dependency_injector.wiring import Provide, inject
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from config.di import Container
from core.domain.access import Level, Scope
from core.http.permissions import scope_permission
from features.gallery.serializers.album_serializers import AlbumSerializer
from features.gallery.serializers.serializers import PhotoSerializer
from features.gallery.serializers.trash_serializers import TrashEntrySerializer
from features.gallery.services.gallery_trash_service import GalleryTrashService

# Overrides above the method defaults (view / manage): the trash shows who deleted and who
# uploaded, and a restore undoes a delete, so both need the level that deletes
# (specs/014-gallery-trash-sync research R-11).
TRASH_OWNER: list[type[BasePermission]] = [
    IsAuthenticated,
    scope_permission(Scope.GALLERY, {"GET": Level.OWNER, "POST": Level.OWNER}),
]


class TrashListAPIView(APIView):
    """``GET`` one entry per deletion batch, most recent first."""

    serializer_class = TrashEntrySerializer
    permission_classes = TRASH_OWNER

    @inject
    def get(
        self,
        request: Request,
        trash_service: GalleryTrashService = Provide[Container.gallery_trash_service],
    ) -> Response:
        entries = trash_service.list_trash()
        return Response(TrashEntrySerializer(entries, many=True, context={"request": request}).data)


class AlbumRestoreAPIView(APIView):
    """``POST`` restores exactly the batch rooted at this album."""

    serializer_class = AlbumSerializer
    permission_classes = TRASH_OWNER

    @inject
    def post(
        self,
        request: Request,
        album_id: int,
        trash_service: GalleryTrashService = Provide[Container.gallery_trash_service],
    ) -> Response:
        album = trash_service.restore_album(album_id)
        return Response(AlbumSerializer(album, context={"request": request}).data)


class PhotoRestoreAPIView(APIView):
    """``POST`` restores a photo that was deleted on its own."""

    serializer_class = PhotoSerializer
    permission_classes = TRASH_OWNER

    @inject
    def post(
        self,
        request: Request,
        photo_id: int,
        trash_service: GalleryTrashService = Provide[Container.gallery_trash_service],
    ) -> Response:
        photo = trash_service.restore_photo(photo_id)
        return Response(PhotoSerializer(photo, context={"request": request}).data)
