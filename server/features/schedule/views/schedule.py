from collections import defaultdict
from datetime import date
from typing import Any

from django.db.models import QuerySet
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from features.accounts.permissions import IsAdminUser
from features.schedule.models.schedule import MonthlySchedule
from features.core.application.services.monthly_scheduler import (
    generate_monthly_schedule_preview,
    save_monthly_schedule,
)
from features.core.http.utils import _not_modified_or_response


def _group_monthly_schedule_qs(schedules: QuerySet[MonthlySchedule]) -> dict[str, Any]:
    grouped: dict[str, Any] = defaultdict(lambda: {"time": None, "items": []})

    for s in schedules:
        key = s.schedule_type.name
        grouped[key]["time"] = s.schedule_type.time.strftime("%H:%M")
        grouped[key]["items"].append(
            {
                "date": s.date.isoformat(),
                "day": s.date.day,
                "member": {"id": s.member_id, "name": s.member.name},
                "schedule_type": {"id": s.schedule_type_id, "name": s.schedule_type.name},
            }
        )

    return grouped


class CurrentMonthlyScheduleAPI(APIView):
    @staticmethod
    def get(request: Request) -> Response:
        today = date.today()

        schedules = (
            MonthlySchedule.objects.filter(year=today.year, month=today.month)
            .select_related("member", "schedule_type")
            .order_by("schedule_type__name", "date")
        )

        result = {
            "year": today.year,
            "month": today.month,
            "schedule": _group_monthly_schedule_qs(schedules),
        }
        return _not_modified_or_response(request, result, status_code=200)


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

    permission_classes = [IsAdminUser]

    def post(self, request: Request) -> Response:
        year = request.data.get("year")
        month = request.data.get("month")
        fixed_list = request.data.get("fixed", []) or []

        fixed_map: dict[tuple[int, date], int] = {}
        for f in fixed_list:
            try:
                schedule_type_id = int(f["schedule_type_id"])
                d = date.fromisoformat(f["date"])
                member_id = int(f["member_id"])
            except (KeyError, ValueError, TypeError):
                continue
            fixed_map[(schedule_type_id, d)] = member_id

        preview = generate_monthly_schedule_preview(
            year=int(year) if year is not None else None,
            month=int(month) if month is not None else None,
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

    permission_classes = [IsAdminUser]

    def post(self, request: Request) -> Response:
        try:
            year = int(request.data["year"])
            month = int(request.data["month"])
            items = request.data.get("items", []) or []

            normalized: list[dict[str, Any]] = []
            for it in items:
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

            save_monthly_schedule(year=year, month=month, items=normalized)
            return Response({"ok": True}, status=200)

        except ValueError as e:
            return Response({"error": str(e)}, status=400)

        except Exception as e:
            return Response({"error": "Erro interno ao salvar escala: " + str(e)}, status=500)
