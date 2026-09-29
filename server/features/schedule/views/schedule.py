from datetime import date
from typing import Any

from dependency_injector.wiring import Provide, inject
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from config.di import Container
from core.domain.access import Scope
from core.domain.exceptions import ValidationError
from core.http.parsing import require_int, require_object_body
from core.http.permissions import IsMemberUser, scope_permission
from core.http.utils import _not_modified_or_response
from features.schedule.services.schedule_service import ScheduleService


class CurrentMonthlyScheduleAPI(APIView):
    permission_classes = [IsMemberUser]

    @staticmethod
    @inject
    def get(
        request: Request,
        schedule_service: ScheduleService = Provide[Container.schedule_service],
    ) -> Response:
        result = schedule_service.get_current_month_schedule(date.today())
        return _not_modified_or_response(request, result, status_code=200, private=True)


class MonthlySchedulePreviewAPI(APIView):
    """
    POST body example:
    {
      "year": 2026,
      "month": 3,
      "fixed": [
        {"schedule_type_id": 1, "date": "2026-03-02", "member_id": 10},
        {"schedule_type_id": 2, "date": "2026-03-09", "member_id": 5}
      ]
    }

    If year/month omitted -> defaults to next month.
    """

    # Persists nothing, but it is a POST that only exists to feed a save: "manage" by method
    # (specs/012-feature-role-permissions, Endpoint Classification).
    permission_classes = [IsAuthenticated, scope_permission(Scope.SCHEDULE)]

    @inject
    def post(
        self,
        request: Request,
        schedule_service: ScheduleService = Provide[Container.schedule_service],
    ) -> Response:
        body = require_object_body(request.data)
        year = body.get("year")
        month = body.get("month")
        fixed_list = body.get("fixed", []) or []

        fixed_map: dict[tuple[int, date], int] = {}
        for f in fixed_list:
            try:
                schedule_type_id = int(f["schedule_type_id"])
                d = date.fromisoformat(f["date"])
                member_id = int(f["member_id"])
            except (KeyError, ValueError, TypeError):
                continue
            fixed_map[(schedule_type_id, d)] = member_id

        preview = schedule_service.generate_preview(
            year=require_int(year, "year") if year is not None else None,
            month=require_int(month, "month") if month is not None else None,
            fixed=fixed_map,
        )
        return Response(preview, status=200)


class MonthlyScheduleSaveAPI(APIView):
    """
    POST body example:
    {
      "year": 2026,
      "month": 3,
      "items": [
        {"date":"2026-03-02","schedule_type_id":1,"member_id":10},
        {"date":"2026-03-09","schedule_type_id":1,"member_id":11}
      ]
    }
    """

    permission_classes = [IsAuthenticated, scope_permission(Scope.SCHEDULE)]

    @inject
    def post(
        self,
        request: Request,
        schedule_service: ScheduleService = Provide[Container.schedule_service],
    ) -> Response:
        # ValidationError and ScheduleOverwriteError bubble up to custom_exception_handler
        year, month, normalized = _parse_schedule_save_payload(request.data)
        schedule_service.save_schedule(year=year, month=month, items=normalized)
        return Response({"ok": True}, status=200)


def _parse_schedule_save_payload(
    data: dict[str, Any],
) -> tuple[int, int, list[dict[str, Any]]]:
    """Extract and validate schedule save payload.

    Raises ``ValidationError`` on invalid input.
    """
    body = require_object_body(data)
    raw_year = body.get("year")
    raw_month = body.get("month")

    if raw_year is None or raw_month is None:
        raise ValidationError("Fields 'year' and 'month' are required.")

    try:
        year = int(raw_year)
        month = int(raw_month)
    except (TypeError, ValueError):
        raise ValidationError("Fields 'year' and 'month' must be integers.")

    items = body.get("items", []) or []

    normalized: list[dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        if "schedule_type_id" in it and "member_id" in it:
            normalized.append(it)
            continue
        try:
            normalized.append(
                {
                    "date": it["date"],
                    "schedule_type_id": it["schedule_type"]["id"],
                    "member_id": it["member"]["id"],
                }
            )
        except (KeyError, TypeError):
            continue

    return year, month, normalized
