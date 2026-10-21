"""Public event reads for the home carousel and the detail screen (specs/020-church-events).

Open to anonymous callers. A valid token of a member adds the members-only events; an invalid
or expired token is ``401`` like on every endpoint, so the app refreshes it (DRF authentication
runs before ``AllowAny``). Bodies depend on the caller, hence private caching.
"""

from dependency_injector.wiring import Provide, inject
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from config.di import Container
from core.http.permissions import IsMemberUser
from core.http.utils import _not_modified_or_response
from features.events.serializers import EventPublicSerializer
from features.events.services.event_service import EventService
from features.events.views.responses import public_body, public_list_body


def _is_member(request: Request, view: APIView) -> bool:
    # The same check the media view uses, so "member" means one thing everywhere.
    return IsMemberUser().has_permission(request, view)


class PublicEventListAPIView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(operation_id="api_events_list", responses=EventPublicSerializer(many=True))
    @inject
    def get(
        self,
        request: Request,
        event_service: EventService = Provide[Container.event_service],
    ) -> Response:
        records = event_service.list_visible(include_members=_is_member(request, self))
        body = public_list_body(request, event_service, records)
        return _not_modified_or_response(request, body, private=True)


class PublicEventDetailAPIView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(operation_id="api_events_retrieve", responses=EventPublicSerializer)
    @inject
    def get(
        self,
        request: Request,
        event_id: int,
        event_service: EventService = Provide[Container.event_service],
    ) -> Response:
        record = event_service.get_visible(event_id, include_members=_is_member(request, self))
        body = public_body(request, event_service, record)
        return _not_modified_or_response(request, body, private=True)
