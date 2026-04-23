from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from features.accounts.permissions import IsMemberUser
from features.gallery.models.gallery import Photo
from features.gallery.serializers.serializers import PhotoListSerializer


class PhotoListAPIView(APIView):
    serializer_class = PhotoListSerializer

    @staticmethod
    def get(request):
        photos = (
            Photo.objects
            .select_related("album")
            .order_by("album__name", "uploaded_at")
        )

        serializer = PhotoListSerializer(
            photos,
            many=True,
            context={"request": request}
        )

        return Response(serializer.data, status=status.HTTP_200_OK)


class AlbumPhotoListAPIView(APIView):
    serializer_class = PhotoListSerializer
    def get(self, request, album_id):
        photos = (
            Photo.objects
            .filter(album_id=album_id)
            .select_related("album")
            .order_by("uploaded_at")
        )

        serializer = PhotoListSerializer(
            photos,
            many=True,
            context={"request": request}
        )

        return Response(serializer.data, status=status.HTTP_200_OK)
