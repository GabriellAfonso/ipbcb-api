from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.persistence.models.profile import Profile

from apps.api.serializers.serializers import ProfilePhotoSerializer, ProfileSerializer
from apps.api.views.utils import _not_modified_or_response


class ProfilePhotoAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @staticmethod
    def post(request):
        """
        Cria ou substitui a foto de perfil do usuário autenticado
        """
        user = request.user

        profile, _ = Profile.objects.get_or_create(user=user)

        serializer = ProfilePhotoSerializer(
            profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "detail": "Foto de perfil atualizada com sucesso.",
                "photo_url": request.build_absolute_uri(profile.photo.url)
                if profile.photo
                else None,
            },
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def delete(request):
        """
        Remove a foto de perfil
        """
        try:
            profile = request.user.profile
        except Profile.DoesNotExist:
            return Response({"detail": "Perfil não encontrado."}, status=404)

        if profile.photo:
            profile.photo.delete(save=False)
            profile.photo = None
            profile.save()

        return Response({"detail": "Foto de perfil removida."}, status=204)


class MeProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @staticmethod
    def get_object(request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        return profile

    def get(self, request):
        profile = self.get_object(request)
        serializer = ProfileSerializer(profile, context={"request": request})
        data = serializer.data
        return _not_modified_or_response(request, data, tag="PROFILE")

    def patch(self, request):
        profile = self.get_object(request)
        serializer = ProfileSerializer(
            profile,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
