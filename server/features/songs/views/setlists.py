"""Sunday setlist endpoints (specs/017-sunday-setlist-push, contracts/setlist-api.md)."""

from typing import cast
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from config.di import Container
from core.domain.access import Level, Scope
from core.http.permissions import IsWorshipMember, scope_permission
from core.http.utils import _not_modified_or_response
from features.songs.services.setlist_service import SetlistService
from features.songs.setlist_dtos import SetlistDTO, parse_setlist_date, parse_setlist_items

# Reading a setlist by date and the pending list serve the register-played side: whoever may
# register plays sees them (``manage``), not every ``view`` holder (spec 017 FR-022, FR-023).
_MANAGERS_ONLY = scope_permission(Scope.SONGS, {"GET": Level.MANAGE})


def setlist_body(setlist: SetlistDTO) -> dict[str, object]:
    """JSON-ready setlist: dates as ``YYYY-MM-DD``, ``saved_at`` ISO 8601 with offset.

    >>> setlist_body(setlist)["date"]
    '2026-10-04'
    """
    return setlist.model_dump(mode="json")


class SetlistByDateAPI(APIView):
    """GET: the setlist of a date. PUT: create or fully replace it (``manage`` on ``songs``
    plus worship membership, checked by the service)."""

    permission_classes = [IsAuthenticated, _MANAGERS_ONLY]

    @inject
    def get(
        self,
        request: Request,
        day: str,
        setlist_service: SetlistService = Provide[Container.setlist_service],
    ) -> Response:
        setlist = setlist_service.by_date(parse_setlist_date(day))
        return _not_modified_or_response(request, setlist_body(setlist), private=True)

    @inject
    def put(
        self,
        request: Request,
        day: str,
        setlist_service: SetlistService = Provide[Container.setlist_service],
    ) -> Response:
        setlist_date = parse_setlist_date(day)
        items = parse_setlist_items(request.data)
        # IsAuthenticated ran, so the user is a real account; songs never imports accounts.
        author_id = cast(UUID, request.user.pk)
        setlist = setlist_service.save(author_id, setlist_date, items)
        return Response(setlist_body(setlist), status=200)


class CurrentSetlistAPI(APIView):
    """The band's fallback when a push does not arrive: the next setlist from today on."""

    permission_classes = [IsAuthenticated, IsWorshipMember]

    @inject
    def get(
        self,
        request: Request,
        setlist_service: SetlistService = Provide[Container.setlist_service],
    ) -> Response:
        setlist = setlist_service.current()
        body = {"setlist": setlist_body(setlist) if setlist else None}
        return _not_modified_or_response(request, body, private=True)


class PendingConfirmationSetlistsAPI(APIView):
    """Setlists whose Sunday came with no played songs registered — the admin panel card."""

    permission_classes = [IsAuthenticated, _MANAGERS_ONLY]

    @inject
    def get(
        self,
        request: Request,
        setlist_service: SetlistService = Provide[Container.setlist_service],
    ) -> Response:
        body = [setlist_body(setlist) for setlist in setlist_service.pending()]
        return _not_modified_or_response(request, body, private=True)
