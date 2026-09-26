from dependency_injector.wiring import Provide, inject
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from config.di import Container
from core.http.permissions import IsAdminUser
from core.http.utils import _not_modified_or_response
from features.members.serializers.admin_member_serializers import ChangeLogEntrySerializer
from features.members.services.member_change_log_service import MemberChangeLogService


class AdminMemberHistoryAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    @inject
    def get(
        self,
        request: Request,
        member_id: int,
        change_log_service: MemberChangeLogService = Provide[Container.member_change_log_service],
    ) -> Response:
        entries = [e.model_dump() for e in change_log_service.list_history(member_id)]
        serializer = ChangeLogEntrySerializer(entries, many=True)
        return _not_modified_or_response(request, {"history": serializer.data}, private=True)
