"""Panel endpoints of Sunday school (specs/026-sunday-school US2–US4).

Access: scope ``sunday_school``, level by method — GET view, POST/PUT/PATCH manage, DELETE owner
(specs/012-feature-role-permissions); Admin and Liderança hold ``owner``, Mídia nothing. GET
answers are private: they hold drafts.
"""

from typing import cast
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
from core.domain.exceptions import ValidationError
from core.http.parsing import require_object_body
from core.http.permissions import scope_permission
from core.http.utils import _not_modified_or_response
from features.sunday_school.dtos import (
    LessonCreateDTO,
    LessonOrderDTO,
    LessonPatchDTO,
    YearThemeDTO,
)
from features.sunday_school.serializers import (
    SundaySchoolLessonCreateSerializer,
    SundaySchoolLessonOrderSerializer,
    SundaySchoolLessonPatchSerializer,
    SundaySchoolLessonSerializer,
    SundaySchoolYearAdminSerializer,
    SundaySchoolYearThemeSerializer,
)
from features.sunday_school.services.management_service import SundaySchoolManagementService
from features.sunday_school.views.query import year_query

_SundaySchoolPermission = scope_permission(Scope.SUNDAY_SCHOOL)

ManagementService = SundaySchoolManagementService
_SERVICE = Provide[Container.sunday_school_management_service]


def _author(request: Request) -> UUID:
    return cast(UUID, request.user.pk)


class _ManageView(APIView):
    permission_classes = [IsAuthenticated, _SundaySchoolPermission]


class SundaySchoolManageLessonsView(_ManageView):
    @extend_schema(
        operation_id="sunday_school_manage_lessons_list",
        parameters=[OpenApiParameter(name="year", type=int, required=True)],
        responses=SundaySchoolLessonSerializer(many=True),
    )
    @inject
    def get(self, request: Request, service: ManagementService = _SERVICE) -> Response:
        year = year_query(request)
        if year is None:
            raise ValidationError("Query parameter 'year' is required, e.g. ?year=2026.")
        body = [lesson.model_dump(mode="json") for lesson in service.lessons_of_year(year)]
        return _not_modified_or_response(request, body, private=True)

    @extend_schema(
        operation_id="sunday_school_manage_lessons_create",
        request=SundaySchoolLessonCreateSerializer,
        responses={201: SundaySchoolLessonSerializer},
    )
    @inject
    def post(self, request: Request, service: ManagementService = _SERVICE) -> Response:
        dto = LessonCreateDTO.model_validate(require_object_body(request.data))
        lesson = service.create(dto, _author(request))
        return Response(lesson.model_dump(mode="json"), status=status.HTTP_201_CREATED)


class SundaySchoolManageLessonDetailView(_ManageView):
    @extend_schema(
        operation_id="sunday_school_manage_lessons_retrieve", responses=SundaySchoolLessonSerializer
    )
    @inject
    def get(
        self, request: Request, lesson_id: int, service: ManagementService = _SERVICE
    ) -> Response:
        body = service.lesson(lesson_id).model_dump(mode="json")
        return _not_modified_or_response(request, body, private=True)

    @extend_schema(
        operation_id="sunday_school_manage_lessons_partial_update",
        request=SundaySchoolLessonPatchSerializer,
        responses=SundaySchoolLessonSerializer,
    )
    @inject
    def patch(
        self, request: Request, lesson_id: int, service: ManagementService = _SERVICE
    ) -> Response:
        patch = LessonPatchDTO.model_validate(require_object_body(request.data))
        lesson = service.update(lesson_id, patch, _author(request))
        return Response(lesson.model_dump(mode="json"))

    @extend_schema(operation_id="sunday_school_manage_lessons_destroy", responses={204: None})
    @inject
    def delete(
        self, request: Request, lesson_id: int, service: ManagementService = _SERVICE
    ) -> Response:
        service.delete(lesson_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SundaySchoolManageOrderView(_ManageView):
    @extend_schema(
        operation_id="sunday_school_manage_lessons_order",
        request=SundaySchoolLessonOrderSerializer,
        responses={204: None},
    )
    @inject
    def put(self, request: Request, service: ManagementService = _SERVICE) -> Response:
        service.set_order(LessonOrderDTO.model_validate(require_object_body(request.data)))
        return Response(status=status.HTTP_204_NO_CONTENT)


class SundaySchoolManageYearsView(_ManageView):
    @extend_schema(
        operation_id="sunday_school_manage_years_list",
        responses=SundaySchoolYearAdminSerializer(many=True),
    )
    @inject
    def get(self, request: Request, service: ManagementService = _SERVICE) -> Response:
        body = [year.model_dump(mode="json") for year in service.years()]
        return _not_modified_or_response(request, body, private=True)


class SundaySchoolManageYearDetailView(_ManageView):
    @extend_schema(
        operation_id="sunday_school_manage_years_partial_update",
        request=SundaySchoolYearThemeSerializer,
        responses=SundaySchoolYearAdminSerializer,
    )
    @inject
    def patch(self, request: Request, year: int, service: ManagementService = _SERVICE) -> Response:
        dto = YearThemeDTO.model_validate(require_object_body(request.data))
        return Response(service.set_theme(year, dto.theme).model_dump(mode="json"))
