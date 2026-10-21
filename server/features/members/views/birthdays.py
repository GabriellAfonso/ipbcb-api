from dependency_injector.wiring import Provide, inject
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from config.di import Container
from core.http.permissions import HasMemberAccess
from features.members.serializers.birthday_serializer import (
    BirthdayQueryParamSerializer,
    BirthdayResponseSerializer,
)
from features.members.services.member_service import MemberService


class MemberBirthdaysAPIView(APIView):
    permission_classes = [IsAuthenticated, HasMemberAccess]

    @inject
    def get(
        self,
        request: Request,
        member_service: MemberService = Provide[Container.member_service],
    ) -> Response:
        param_serializer = BirthdayQueryParamSerializer(data=request.query_params)
        if not param_serializer.is_valid():
            return Response(param_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        start_month, end_month = param_serializer.validated_data["month"]
        birthdays = member_service.list_birthdays_by_month_range(start_month, end_month)

        serializer = BirthdayResponseSerializer([b.model_dump() for b in birthdays], many=True)
        return Response({"birthdays": serializer.data}, status=status.HTTP_200_OK)
