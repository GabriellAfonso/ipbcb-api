"""HTTP surface for hymnal view history.

Ingest and the settings read are ``AllowAny`` by design: most members use the
hymnal without logging in, and a fresh install must learn the view threshold
before anyone authenticates. Everything else is scope ``reports.hymnal_history``: reads need
``view``, configuration writes ``owner`` by override, so only Admin configures
(specs/012-feature-role-permissions).
"""

from datetime import date, timedelta
from typing import Any
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from drf_spectacular.utils import extend_schema
from pydantic import ValidationError as PydanticValidationError
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from config.di import Container
from core.domain.access import Level, Scope
from core.http.parsing import require_object_body
from core.http.permissions import scope_permission
from features.songs.hymnal_history_dtos import (
    REASON_INVALID_EVENT,
    HymnViewEventInput,
    RejectedEventDTO,
    ReportRangeDTO,
    ServiceWindowDTO,
)
from features.songs.serializers.hymnal_history_serializers import (
    HymnalHistorySettingsSerializer,
    IngestEnvelopeSerializer,
    IngestResultSerializer,
    OccurrenceQueryParamSerializer,
    OccurrenceSerializer,
    ServiceWindowSerializer,
    TopHymnSerializer,
    TopHymnsQueryParamSerializer,
)
from features.songs.services.hymnal_history_config_service import HymnalHistoryConfigService
from features.songs.services.hymnal_history_ingest_service import HymnalHistoryIngestService
from features.songs.services.hymnal_history_report_service import (
    DEFAULT_RANGE_DAYS,
    HymnalHistoryReportService,
)


_REPORT_SCOPE = Scope.REPORTS_HYMNAL_HISTORY
# Configuration writes are owner-only by override: a report can be released to a role for
# reading without letting it change how the report is computed. DELETE is owner by default.
_CONFIG_WRITE = {"POST": Level.OWNER, "PATCH": Level.OWNER}
_ReportPermission = scope_permission(_REPORT_SCOPE)
_ConfigPermission = scope_permission(_REPORT_SCOPE, _CONFIG_WRITE)


def _parse_events(
    raw_events: list[dict[str, Any]],
) -> tuple[list[HymnViewEventInput], list[RejectedEventDTO]]:
    """Split the batch into parseable events and per-event parse failures.

    A malformed event is rejected individually so it can never block the rest of
    the batch. An event without a usable ``client_event_id`` is dropped silently —
    there is no id to answer for, and the app has nothing to delete.
    """
    parsed: list[HymnViewEventInput] = []
    rejected: list[RejectedEventDTO] = []

    for raw in raw_events:
        try:
            parsed.append(HymnViewEventInput(**raw))
        except (PydanticValidationError, TypeError):
            client_event_id = raw.get("client_event_id")
            if client_event_id is None:
                continue
            try:
                rejected.append(
                    RejectedEventDTO(client_event_id=client_event_id, reason=REASON_INVALID_EVENT)
                )
            except PydanticValidationError:
                continue

    return parsed, rejected


class HymnalHistoryIngestAPI(APIView):
    """POST: store a batch of hymn views synced by the app.

    Unauthenticated writes are accepted deliberately, throttled per client address.
    A valid JWT attributes the events to that user; otherwise they are anonymous.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "hymnal_ingest"

    @extend_schema(
        request=IngestEnvelopeSerializer,
        responses={201: IngestResultSerializer},
    )
    @inject
    def post(
        self,
        request: Request,
        ingest_service: HymnalHistoryIngestService = Provide[
            Container.hymnal_history_ingest_service
        ],
    ) -> Response:
        envelope = IngestEnvelopeSerializer(data=request.data)
        envelope.is_valid(raise_exception=True)

        parsed, unparseable = _parse_events(envelope.validated_data["events"])
        # The user model's primary key is a UUID, not an integer.
        user_id: UUID | None = (
            request.user.id if request.user and request.user.is_authenticated else None
        )

        result = ingest_service.ingest(parsed, user_id=user_id)
        result.rejected.extend(unparseable)

        return Response(IngestResultSerializer(result.model_dump()).data, status=201)


class HymnalHistoryOccurrencesAPI(APIView):
    """GET: the occurrences in a period, grouped."""

    permission_classes = [IsAuthenticated, _ReportPermission]

    @extend_schema(
        parameters=[OccurrenceQueryParamSerializer],
        responses={200: OccurrenceSerializer(many=True)},
    )
    @inject
    def get(
        self,
        request: Request,
        report_service: HymnalHistoryReportService = Provide[
            Container.hymnal_history_report_service
        ],
    ) -> Response:
        params = OccurrenceQueryParamSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)

        to_date = params.validated_data.get("to") or date.today()
        from_date = params.validated_data.get("from") or to_date - timedelta(
            days=DEFAULT_RANGE_DAYS
        )
        group_by = params.validated_data["group_by"]

        occurrences = report_service.list_occurrences(
            ReportRangeDTO(from_date=from_date, to_date=to_date, group_by=group_by)
        )

        return Response(
            {
                "from": from_date,
                "to": to_date,
                "group_by": group_by,
                "occurrences": OccurrenceSerializer(
                    [o.model_dump() for o in occurrences], many=True
                ).data,
            }
        )


class HymnalHistoryTopHymnsAPI(APIView):
    """GET: hymns ranked by how many times the congregation sang them."""

    permission_classes = [IsAuthenticated, _ReportPermission]

    @extend_schema(
        parameters=[TopHymnsQueryParamSerializer],
        responses={200: TopHymnSerializer(many=True)},
    )
    @inject
    def get(
        self,
        request: Request,
        report_service: HymnalHistoryReportService = Provide[
            Container.hymnal_history_report_service
        ],
    ) -> Response:
        params = TopHymnsQueryParamSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)

        from_date = params.validated_data.get("from")
        to_date = params.validated_data.get("to")
        ranked = report_service.top_hymns(from_date, to_date)

        return Response(
            {
                "from": from_date,
                "to": to_date,
                "hymns": TopHymnSerializer([h.model_dump() for h in ranked], many=True).data,
            }
        )


class HymnalHistorySettingsAPI(APIView):
    """GET (public): the app reads the view threshold on startup. PATCH: owner only."""

    def get_permissions(self) -> list[BasePermission]:
        if self.request.method == "PATCH":
            return [IsAuthenticated(), _ConfigPermission()]
        return [AllowAny()]

    @extend_schema(responses={200: HymnalHistorySettingsSerializer})
    @inject
    def get(
        self,
        request: Request,
        config_service: HymnalHistoryConfigService = Provide[
            Container.hymnal_history_config_service
        ],
    ) -> Response:
        settings = config_service.get_settings()
        return Response(HymnalHistorySettingsSerializer(settings.model_dump()).data)

    @extend_schema(
        request=HymnalHistorySettingsSerializer,
        responses={200: HymnalHistorySettingsSerializer},
    )
    @inject
    def patch(
        self,
        request: Request,
        config_service: HymnalHistoryConfigService = Provide[
            Container.hymnal_history_config_service
        ],
    ) -> Response:
        serializer = HymnalHistorySettingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        updated = config_service.update_settings(serializer.validated_data)
        return Response(HymnalHistorySettingsSerializer(updated.model_dump()).data)


class ServiceWindowListCreateAPI(APIView):
    """GET: list every service window. POST: create one."""

    permission_classes = [IsAuthenticated, _ConfigPermission]

    @extend_schema(responses={200: ServiceWindowSerializer(many=True)})
    @inject
    def get(
        self,
        request: Request,
        config_service: HymnalHistoryConfigService = Provide[
            Container.hymnal_history_config_service
        ],
    ) -> Response:
        windows = config_service.list_windows()
        data = ServiceWindowSerializer([w.model_dump() for w in windows], many=True).data
        return Response({"service_windows": data})

    @extend_schema(request=ServiceWindowSerializer, responses={201: ServiceWindowSerializer})
    @inject
    def post(
        self,
        request: Request,
        config_service: HymnalHistoryConfigService = Provide[
            Container.hymnal_history_config_service
        ],
    ) -> Response:
        serializer = ServiceWindowSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        created = config_service.create_window(ServiceWindowDTO(**serializer.validated_data))
        return Response(ServiceWindowSerializer(created.model_dump()).data, status=201)


class ServiceWindowDetailAPI(APIView):
    """GET / PATCH / DELETE a single service window.

    Editing or deleting a window never touches a stored event — occurrences are
    derived at read time, so only the interpretation changes.
    """

    permission_classes = [IsAuthenticated, _ConfigPermission]

    @extend_schema(responses={200: ServiceWindowSerializer})
    @inject
    def get(
        self,
        request: Request,
        pk: int,
        config_service: HymnalHistoryConfigService = Provide[
            Container.hymnal_history_config_service
        ],
    ) -> Response:
        window = config_service.get_window(pk)
        return Response(ServiceWindowSerializer(window.model_dump()).data)

    @extend_schema(request=ServiceWindowSerializer, responses={200: ServiceWindowSerializer})
    @inject
    def patch(
        self,
        request: Request,
        pk: int,
        config_service: HymnalHistoryConfigService = Provide[
            Container.hymnal_history_config_service
        ],
    ) -> Response:
        current = config_service.get_window(pk)

        # Validate the merged result, so a PATCH touching only start_time is still
        # checked against the stored end_time instead of hitting the DB constraint.
        merged = {**current.model_dump(), **require_object_body(request.data)}
        merged.pop("id", None)
        serializer = ServiceWindowSerializer(data=merged)
        serializer.is_valid(raise_exception=True)

        changes = {k: v for k, v in serializer.validated_data.items() if k in request.data}
        updated = config_service.update_window(pk, changes)
        return Response(ServiceWindowSerializer(updated.model_dump()).data)

    @extend_schema(responses={204: None})
    @inject
    def delete(
        self,
        request: Request,
        pk: int,
        config_service: HymnalHistoryConfigService = Provide[
            Container.hymnal_history_config_service
        ],
    ) -> Response:
        config_service.delete_window(pk)
        return Response(status=204)
