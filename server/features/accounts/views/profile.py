from typing import NamedTuple, cast

from dependency_injector.wiring import inject, Provide
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from features.accounts.models.profile import Profile
from features.accounts.models.user import User
from features.accounts.serializers.serializers import ProfileSerializer
from features.accounts.services.access_request_service import AccessRequestService
from features.accounts.services.profile_service import ProfileService
from config.di import Container
from core.application.access_service import AccessService
from core.application.worship_access_service import WorshipAccessService
from core.http.utils import _not_modified_or_response


class ProfilePhotoAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @inject
    def post(
        self,
        request: Request,
        profile_service: ProfileService = Provide[Container.profile_service],
    ) -> Response:
        user = cast(User, request.user)
        photo = request.FILES.get("photo")
        if not photo:
            return Response({"detail": "Nenhuma foto enviada."}, status=status.HTTP_400_BAD_REQUEST)

        # The file object is handed over whole: the service validates it and the
        # repository streams it, so the upload is never materialised in memory here.
        profile = profile_service.upload_photo(user, photo)

        return Response(
            {
                "detail": "Foto de perfil atualizada com sucesso.",
                "photo_url": request.build_absolute_uri(profile.photo.url)
                if profile.photo
                else None,
            },
            status=status.HTTP_200_OK,
        )

    @inject
    def delete(
        self,
        request: Request,
        profile_service: ProfileService = Provide[Container.profile_service],
    ) -> Response:
        user = cast(User, request.user)
        profile_service.delete_photo(user)
        return Response({"detail": "Foto de perfil removida."}, status=status.HTTP_204_NO_CONTENT)


class MeProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @inject
    def get(
        self,
        request: Request,
        profile_service: ProfileService = Provide[Container.profile_service],
        access_service: AccessService = Provide[Container.access_service],
        worship_access_service: WorshipAccessService = Provide[Container.worship_access_service],
        access_request_service: AccessRequestService = Provide[Container.access_request_service],
    ) -> Response:
        user = cast(User, request.user)
        profile = profile_service.get_profile(user)
        services = _ContextServices(access_service, worship_access_service, access_request_service)
        serializer = ProfileSerializer(
            profile, context=_serializer_context(request, user, profile, services)
        )
        data = serializer.data
        return _not_modified_or_response(request, data, private=True)

    @inject
    def patch(
        self,
        request: Request,
        profile_service: ProfileService = Provide[Container.profile_service],
        access_service: AccessService = Provide[Container.access_service],
        worship_access_service: WorshipAccessService = Provide[Container.worship_access_service],
        access_request_service: AccessRequestService = Provide[Container.access_request_service],
    ) -> Response:
        user = cast(User, request.user)
        profile = profile_service.get_profile(user)
        services = _ContextServices(access_service, worship_access_service, access_request_service)
        context = _serializer_context(request, user, profile, services)
        # The serializer only validates; the write goes through the service like every other
        # one. Read-only fields never reach validated_data, so only `name` can be written.
        serializer = ProfileSerializer(data=request.data, partial=True, context=context)
        serializer.is_valid(raise_exception=True)
        profile = profile_service.update_profile(user, **serializer.validated_data)
        return Response(ProfileSerializer(profile, context=context).data, status=status.HTTP_200_OK)


class _ContextServices(NamedTuple):
    access: AccessService
    worship: WorshipAccessService
    access_requests: AccessRequestService


def _serializer_context(
    request: Request, user: User, profile: Profile, services: _ContextServices
) -> dict[str, object]:
    """The profile carries the caller's panel roles, so the app decides from one read whether
    to show the panel (specs/012-feature-role-permissions US4), the worship flags, so it
    knows whether to offer setlist screens (specs/017-sunday-setlist-push US4), and the member
    access state, so it knows which screens to lock (specs/022-access-requests FR-004).

    >>> _serializer_context(request, user, profile, services)["access_grants"].roles
    [<Role.LEADER: 'leader'>]
    """
    grants = services.access.grants_for(user.pk)
    return {
        "request": request,
        "access_grants": grants,
        "worship_flags": services.worship.flags_for(user.pk, grants),
        "member_access_state": services.access_requests.access_state(
            user.pk, profile.member_access, grants.roles
        ),
    }
