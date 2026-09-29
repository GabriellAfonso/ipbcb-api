from dependency_injector.wiring import Provide, inject
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from config.di import Container
from core.domain.exceptions import ValidationError
from features.gallery.serializers.album_serializers import AlbumSerializer
from features.gallery.services.album_cover_service import AlbumCoverService
from features.gallery.services.album_service import AlbumService
from features.gallery.views.gallery import GALLERY_WRITE


class AlbumCoverAPIView(APIView):
    """An album's own cover: ``PUT`` needs ``manage`` on gallery, ``DELETE`` ``owner`` — held
    by Admin, Liderança and Mídia (specs/013-gallery-write-api FR-003)."""

    serializer_class = AlbumSerializer
    permission_classes = GALLERY_WRITE
    parser_classes = [MultiPartParser, FormParser]

    @inject
    def put(
        self,
        request: Request,
        album_id: int,
        cover_service: AlbumCoverService = Provide[Container.album_cover_service],
        album_service: AlbumService = Provide[Container.album_service],
    ) -> Response:
        upload = request.FILES.get("image")
        if not upload:
            raise ValidationError("Nenhuma imagem enviada. Envie o arquivo no campo 'image'.")
        # Handed over whole: the service validates it before anything is stored.
        cover_service.replace_cover(album_id, upload)
        album = album_service.view_of(album_id)
        return Response(AlbumSerializer(album, context={"request": request}).data)

    @inject
    def delete(
        self,
        request: Request,
        album_id: int,
        cover_service: AlbumCoverService = Provide[Container.album_cover_service],
    ) -> Response:
        cover_service.remove_cover(album_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
