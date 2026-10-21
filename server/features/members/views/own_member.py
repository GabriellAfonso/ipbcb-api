"""The caller's own roll record, for the profile screen (specs/022-access-requests FR-023).

Kept out of ``api/me/profile/`` on purpose: the app writes that response to disk (ETag
snapshot), and roll data is sensitive (constitution, members domain). This one is
``private, no-store`` with no validator, so the phone keeps it in memory only.
"""

from typing import cast
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from config.di import Container
from features.members.serializers.own_member_serializer import OwnMemberSerializer
from features.members.services.member_service import MemberService


def _never_stored(response: Response) -> Response:
    """No ETag on purpose: a validator invites the client to keep the body."""
    response["Cache-Control"] = "private, no-store"
    response["Vary"] = "Authorization"
    return response


class OwnMemberAPIView(APIView):
    """GET: the roll record linked to the caller's account. Only ``IsAuthenticated``: it is the
    caller's own data, readable with or without member access."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses=OwnMemberSerializer)
    @inject
    def get(
        self,
        request: Request,
        member_service: MemberService = Provide[Container.member_service],
    ) -> Response:
        record = member_service.get_own_record(cast(UUID, request.user.pk))
        body = OwnMemberSerializer(record.model_dump()).data
        return _never_stored(Response(body, status=status.HTTP_200_OK))
