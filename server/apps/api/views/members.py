from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from apps.api.permissions import IsMemberUser
from apps.persistence.models.member import Member


class MemberListAPIView(APIView):
    permission_classes = [IsAuthenticated, IsMemberUser]

    @staticmethod
    def get(request):
        members = (
            Member.objects
            .filter(is_active=True)
            .only("id", "name")
            .order_by("name")
        )

        data = {
            "members": [
                {"id": m.id, "name": m.name}
                for m in members
            ]
        }

        return Response(data, status=status.HTTP_200_OK)