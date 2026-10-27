"""Public Sunday school endpoints (specs/026-sunday-school US1): published lessons only, no
sign-in, ``ETag`` / 304 like doctrine; responses are not marked private."""

from dependency_injector.wiring import Provide, inject
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from config.di import Container
from core.http.utils import _not_modified_or_response
from features.sunday_school.serializers import (
    SundaySchoolLessonSerializer,
    SundaySchoolIndexSerializer,
)
from features.sunday_school.services.reading_service import SundaySchoolReadingService
from features.sunday_school.views.query import year_query

_YEAR_PARAMETER = OpenApiParameter(
    name="year", type=int, required=False, description="Absent = the default year"
)


class SundaySchoolIndexView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="sunday_school_index",
        parameters=[_YEAR_PARAMETER],
        responses={200: SundaySchoolIndexSerializer, 304: None, 404: None},
    )
    @inject
    def get(
        self,
        request: Request,
        reading_service: SundaySchoolReadingService = Provide[
            Container.sunday_school_reading_service
        ],
    ) -> Response:
        index = reading_service.index(year_query(request))
        return _not_modified_or_response(request, index.model_dump(mode="json"))


class SundaySchoolLessonView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="sunday_school_lesson",
        responses={200: SundaySchoolLessonSerializer, 304: None, 404: None},
    )
    @inject
    def get(
        self,
        request: Request,
        lesson_id: int,
        reading_service: SundaySchoolReadingService = Provide[
            Container.sunday_school_reading_service
        ],
    ) -> Response:
        lesson = reading_service.lesson(lesson_id)
        return _not_modified_or_response(request, lesson.model_dump(mode="json"))
