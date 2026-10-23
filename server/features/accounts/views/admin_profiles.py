"""Perfis: app accounts and their access requests (specs/022-access-requests).

Access: scope ``profiles``, level by method — GET view, POST/PATCH manage
(specs/012-feature-role-permissions). Admin ``owner``, Liderança ``manage``, Mídia nothing.
"""

from typing import Any, cast
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from config.di import Container
from core.domain.access import Scope
from core.http.parsing import optional_single_value, require_object_body
from core.http.permissions import scope_permission
from core.http.utils import _not_modified_or_response
from features.accounts.dtos import ManagedAccountDetailDTO
from features.accounts.serializers.access_request_serializers import (
    AccessDenySerializer,
    ManagedAccountDetailSerializer,
    ManagedAccountPatchSerializer,
    ManagedAccountSerializer,
)
from features.accounts.services.profile_management_service import ProfileManagementService

_ProfilesPermission = scope_permission(Scope.PROFILES)

_STATUS_PARAMETER = OpenApiParameter(
    name="status", enum=["pending", "all"], default="all", required=False
)


def _detail_body(request: Request, account: ManagedAccountDetailDTO) -> dict[str, Any]:
    serializer = ManagedAccountDetailSerializer(account.model_dump(), context={"request": request})
    return dict(serializer.data)


def _detail_response(request: Request, account: ManagedAccountDetailDTO) -> Response:
    return Response(_detail_body(request, account), status=status.HTTP_200_OK)


class AdminProfileListAPIView(APIView):
    permission_classes = [IsAuthenticated, _ProfilesPermission]

    @extend_schema(
        operation_id="api_admin_profiles_list",
        parameters=[_STATUS_PARAMETER],
        responses=ManagedAccountSerializer(many=True),
    )
    @inject
    def get(
        self,
        request: Request,
        service: ProfileManagementService = Provide[Container.profile_management_service],
    ) -> Response:
        status_raw = optional_single_value(request.query_params.getlist("status"), "status")
        accounts = service.list_accounts(status_raw)
        dumps = [account.model_dump() for account in accounts]
        serializer = ManagedAccountSerializer(dumps, many=True, context={"request": request})
        return _not_modified_or_response(request, {"accounts": serializer.data}, private=True)


class AdminProfileDetailAPIView(APIView):
    permission_classes = [IsAuthenticated, _ProfilesPermission]

    @extend_schema(
        operation_id="api_admin_profiles_retrieve", responses=ManagedAccountDetailSerializer
    )
    @inject
    def get(
        self,
        request: Request,
        user_id: UUID,
        service: ProfileManagementService = Provide[Container.profile_management_service],
    ) -> Response:
        body = _detail_body(request, service.get_account(user_id))
        return _not_modified_or_response(request, body, private=True)

    @extend_schema(request=ManagedAccountPatchSerializer, responses=ManagedAccountDetailSerializer)
    @inject
    def patch(
        self,
        request: Request,
        user_id: UUID,
        service: ProfileManagementService = Provide[Container.profile_management_service],
    ) -> Response:
        serializer = ManagedAccountPatchSerializer(data=require_object_body(request.data))
        serializer.is_valid(raise_exception=True)
        return _detail_response(request, service.update_account(user_id, serializer.create_dto()))


class AdminProfileGrantAccessAPIView(APIView):
    """POST: set the stored member-access flag without a request; approval push to the account."""

    permission_classes = [IsAuthenticated, _ProfilesPermission]

    @extend_schema(request=None, responses=ManagedAccountDetailSerializer)
    @inject
    def post(
        self,
        request: Request,
        user_id: UUID,
        service: ProfileManagementService = Provide[Container.profile_management_service],
    ) -> Response:
        leader_id = cast(UUID, request.user.pk)
        return _detail_response(request, service.grant_access(user_id, leader_id))


class AdminProfileRevokeAccessAPIView(APIView):
    """POST: clear the stored member-access flag. No push."""

    permission_classes = [IsAuthenticated, _ProfilesPermission]

    @extend_schema(request=None, responses=ManagedAccountDetailSerializer)
    @inject
    def post(
        self,
        request: Request,
        user_id: UUID,
        service: ProfileManagementService = Provide[Container.profile_management_service],
    ) -> Response:
        return _detail_response(request, service.revoke_access(user_id))


class AdminAccessRequestApproveAPIView(APIView):
    permission_classes = [IsAuthenticated, _ProfilesPermission]

    @extend_schema(request=None, responses=ManagedAccountDetailSerializer)
    @inject
    def post(
        self,
        request: Request,
        request_id: int,
        service: ProfileManagementService = Provide[Container.profile_management_service],
    ) -> Response:
        leader_id = cast(UUID, request.user.pk)
        return _detail_response(request, service.approve(request_id, leader_id))


class AdminAccessRequestDenyAPIView(APIView):
    permission_classes = [IsAuthenticated, _ProfilesPermission]

    @extend_schema(request=AccessDenySerializer, responses=ManagedAccountDetailSerializer)
    @inject
    def post(
        self,
        request: Request,
        request_id: int,
        service: ProfileManagementService = Provide[Container.profile_management_service],
    ) -> Response:
        # An empty body is a denial without reason.
        body = require_object_body(request.data) if request.data else {}
        serializer = AccessDenySerializer(data=body)
        serializer.is_valid(raise_exception=True)
        leader_id = cast(UUID, request.user.pk)
        reason = serializer.validated_data.get("reason")
        return _detail_response(request, service.deny(request_id, leader_id, reason))
