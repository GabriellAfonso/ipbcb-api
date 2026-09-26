"""Leader endpoints for the membership roll (specs/010-members-management).

Leader = ``Profile.is_admin``, checked by ``IsAdminUser`` on every view. Every GET is private:
member data must never be stored by a shared cache.
"""

from typing import cast
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from config.di import Container
from core.http.parsing import require_object_body
from core.http.permissions import IsAdminUser
from core.http.utils import _not_modified_or_response
from features.members.dtos import MemberCreateDTO, MemberPatchDTO, MemberRecordDTO
from features.members.serializers.admin_member_serializers import (
    MemberCreateSerializer,
    MemberOptionsSerializer,
    MemberPatchSerializer,
    MemberRecordSerializer,
    MemberSummarySerializer,
)
from features.members.services.member_roster_service import MemberRosterService


def editor_id_of(request: Request) -> UUID:
    """The caller's user id, recorded as the editor in the member history.

    >>> editor_id_of(request)
    UUID('5b0e...')
    """
    return cast(UUID, request.user.pk)


def _record_body(request: Request, record: MemberRecordDTO) -> dict[str, object]:
    serializer = MemberRecordSerializer(record.model_dump(), context={"request": request})
    return dict(serializer.data)


class AdminMemberListAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    @inject
    def get(
        self,
        request: Request,
        roster_service: MemberRosterService = Provide[Container.member_roster_service],
    ) -> Response:
        members = [m.model_dump() for m in roster_service.list_members()]
        serializer = MemberSummarySerializer(members, many=True, context={"request": request})
        return _not_modified_or_response(request, {"members": serializer.data}, private=True)

    @inject
    def post(
        self,
        request: Request,
        roster_service: MemberRosterService = Provide[Container.member_roster_service],
    ) -> Response:
        serializer = MemberCreateSerializer(data=require_object_body(request.data))
        serializer.is_valid(raise_exception=True)
        dto = MemberCreateDTO.model_validate(serializer.validated_data)
        record = roster_service.create_member(dto, editor_id_of(request))
        return Response(_record_body(request, record), status=status.HTTP_201_CREATED)


class AdminMemberDetailAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    @inject
    def get(
        self,
        request: Request,
        member_id: int,
        roster_service: MemberRosterService = Provide[Container.member_roster_service],
    ) -> Response:
        record = roster_service.get_member(member_id)
        return _not_modified_or_response(request, _record_body(request, record), private=True)

    @inject
    def patch(
        self,
        request: Request,
        member_id: int,
        roster_service: MemberRosterService = Provide[Container.member_roster_service],
    ) -> Response:
        serializer = MemberPatchSerializer(data=require_object_body(request.data), partial=True)
        serializer.is_valid(raise_exception=True)
        # Only the keys the app sent are in validated_data, so model_fields_set tells
        # "leave alone" from "clear".
        dto = MemberPatchDTO.model_validate(serializer.validated_data)
        record = roster_service.update_member(member_id, dto, editor_id_of(request))
        return Response(_record_body(request, record), status=status.HTTP_200_OK)

    @inject
    def delete(
        self,
        request: Request,
        member_id: int,
        roster_service: MemberRosterService = Provide[Container.member_roster_service],
    ) -> Response:
        roster_service.delete_member(member_id, editor_id_of(request))
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminMemberOptionsAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    @inject
    def get(
        self,
        request: Request,
        roster_service: MemberRosterService = Provide[Container.member_roster_service],
    ) -> Response:
        options = roster_service.get_options()
        serializer = MemberOptionsSerializer(options.model_dump())
        return _not_modified_or_response(request, serializer.data, private=True)
