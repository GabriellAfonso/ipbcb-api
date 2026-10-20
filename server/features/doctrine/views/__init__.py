from dependency_injector.wiring import Provide, inject
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from config.di import Container
from core.http.utils import _not_modified_or_response
from features.doctrine.serializers import DOCTRINE_DOCUMENT_SCHEMA, DoctrineDocumentListSerializer
from features.doctrine.services import DoctrineService


class DoctrineListView(APIView):
    permission_classes = [AllowAny]

    # Explicit operation ids for the generated Android client, as in the Bible views.
    @extend_schema(
        operation_id="doctrine_documents_list",
        responses={200: DoctrineDocumentListSerializer, 304: None},
    )
    @inject
    def get(
        self,
        request: Request,
        doctrine_service: DoctrineService = Provide[Container.doctrine_service],
    ) -> Response:
        summaries = doctrine_service.list_documents()
        body = {"documents": [summary.model_dump() for summary in summaries]}
        return _not_modified_or_response(request, body)


class DoctrineDetailView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="doctrine_document_retrieve",
        responses={200: DOCTRINE_DOCUMENT_SCHEMA, 304: None, 404: None},
    )
    @inject
    def get(
        self,
        request: Request,
        slug: str,
        doctrine_service: DoctrineService = Provide[Container.doctrine_service],
    ) -> Response:
        # DoctrineDocumentNotFoundError bubbles up to custom_exception_handler.
        document = doctrine_service.get_document(slug)
        # exclude_unset, not exclude_none: a paragraph without a list omits ``lists`` and
        # ``text_after``, while a proof text keeps its explicit ``"reference": null``.
        return _not_modified_or_response(request, document.model_dump(exclude_unset=True))
