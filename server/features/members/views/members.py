from dependency_injector.wiring import Provide, inject
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from config.di import Container
from core.domain.access import Scope
from core.http.permissions import IsMemberUser, scope_permission
from features.members.services.member_service import MemberService


class MemberListAPIView(APIView):
    # The schedule screen lists members to roster, and a Liderança or Admin managing the
    # schedule is not necessarily flagged as a member (specs/012-feature-role-permissions FR-031).
    permission_classes = [IsAuthenticated, IsMemberUser | scope_permission(Scope.SCHEDULE)]

    @inject
    def get(
        self,
        request: Request,
        member_service: MemberService = Provide[Container.member_service],
    ) -> Response:
        members = member_service.list_active_members()
        data = {"members": [m.model_dump() for m in members]}
        return Response(data, status=status.HTTP_200_OK)
