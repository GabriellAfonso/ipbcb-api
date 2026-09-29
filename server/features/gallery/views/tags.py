from dependency_injector.wiring import Provide, inject
from rest_framework.parsers import JSONParser
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from config.di import Container
from core.domain.access import Level, Scope
from core.http.parsing import require_object_body
from core.http.permissions import IsMemberUser, scope_permission
from core.http.utils import _not_modified_or_response
from features.gallery.dtos.tag_dtos import PhotoMembersReplace, PhotoTagsBulkChange
from features.gallery.serializers.serializers import MemberRefSerializer, PhotoSerializer
from features.gallery.serializers.tag_serializers import (
    PhotoMembersReplaceSerializer,
    PhotoTagsBulkSerializer,
    TaggedMemberSerializer,
)
from features.gallery.services.photo_tag_service import PhotoTagService
from features.gallery.views.gallery import GALLERY_WRITE

# Override above the GET default (view): the picker lists every member of the roll, so it takes
# the level that tags. It is the one place the Mídia role reads member data, and only names
# (specs/015-gallery-member-tags FR-031; spec 012 User Story 3).
TAG_PICKER: list[type[BasePermission]] = [
    IsAuthenticated,
    scope_permission(Scope.GALLERY, {"GET": Level.MANAGE}),
]


class PhotoMembersAPIView(APIView):
    """``PUT`` the full set of members tagged in one photo."""

    serializer_class = PhotoMembersReplaceSerializer
    permission_classes = GALLERY_WRITE
    parser_classes = [JSONParser]

    @inject
    def put(
        self,
        request: Request,
        photo_id: int,
        tag_service: PhotoTagService = Provide[Container.photo_tag_service],
    ) -> Response:
        serializer = PhotoMembersReplaceSerializer(data=require_object_body(request.data))
        serializer.is_valid(raise_exception=True)
        change = PhotoMembersReplace(**serializer.validated_data)
        photo = tag_service.replace_photo_members(photo_id, change, request.user.pk)
        return Response(PhotoSerializer(photo, context={"request": request}).data)


class PhotoTagsBulkAPIView(APIView):
    """``POST`` tags to add and remove on many photos; every other tag stays."""

    serializer_class = PhotoTagsBulkSerializer
    permission_classes = GALLERY_WRITE
    parser_classes = [JSONParser]

    @inject
    def post(
        self,
        request: Request,
        tag_service: PhotoTagService = Provide[Container.photo_tag_service],
    ) -> Response:
        serializer = PhotoTagsBulkSerializer(data=require_object_body(request.data))
        serializer.is_valid(raise_exception=True)
        change = PhotoTagsBulkChange(**serializer.validated_data)
        photos = tag_service.change_tags(change, request.user.pk)
        return Response(PhotoSerializer(photos, many=True, context={"request": request}).data)


class TaggableMembersAPIView(APIView):
    """``GET`` the tag picker: every member, active or not, id and name only."""

    serializer_class = MemberRefSerializer
    permission_classes = TAG_PICKER

    @inject
    def get(
        self,
        request: Request,
        tag_service: PhotoTagService = Provide[Container.photo_tag_service],
    ) -> Response:
        data = MemberRefSerializer(tag_service.taggable_members(), many=True).data
        # Private: names from the roll never go to a shared cache (spec 015 FR-034).
        return _not_modified_or_response(request, data, private=True)


class TaggedMembersAPIView(APIView):
    """``GET`` the members tagged in at least one live photo, with how many."""

    serializer_class = TaggedMemberSerializer
    permission_classes = [IsMemberUser]

    @inject
    def get(
        self,
        request: Request,
        tag_service: PhotoTagService = Provide[Container.photo_tag_service],
    ) -> Response:
        data = TaggedMemberSerializer(tag_service.tagged_members(), many=True).data
        return _not_modified_or_response(request, data, private=True)
