from dependency_injector.wiring import Provide, inject
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from config.di import Container
from core.domain.exceptions import ValidationError
from core.http.permissions import IsAdminUser
from features.members.serializers.admin_member_serializers import build_photo_url
from features.members.services.member_photo_service import MemberPhotoService
from features.members.views.admin_members import editor_id_of


class AdminMemberPhotoAPIView(APIView):
    """Leader-only member photo. Reading it goes through the media access check, which
    allows ``members/`` to leaders alone (specs/009-protected-media-access)."""

    permission_classes = [IsAuthenticated, IsAdminUser]
    parser_classes = [MultiPartParser, FormParser]

    @inject
    def put(
        self,
        request: Request,
        member_id: int,
        photo_service: MemberPhotoService = Provide[Container.member_photo_service],
    ) -> Response:
        photo = request.FILES.get("photo")
        if not photo:
            raise ValidationError("Nenhuma foto enviada. Envie o arquivo no campo 'photo'.")
        # Handed over whole: the service validates it and the storage streams it.
        photo_path = photo_service.replace_photo(member_id, photo, editor_id_of(request))
        return Response(
            {"photo_url": build_photo_url(request, photo_path)}, status=status.HTTP_200_OK
        )

    @inject
    def delete(
        self,
        request: Request,
        member_id: int,
        photo_service: MemberPhotoService = Provide[Container.member_photo_service],
    ) -> Response:
        photo_service.remove_photo(member_id, editor_id_of(request))
        return Response(status=status.HTTP_204_NO_CONTENT)
