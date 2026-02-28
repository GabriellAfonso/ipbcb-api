from collections import defaultdict
from datetime import date

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.persistence.models.schedule import MonthlySchedule
from core.application.services.monthly_scheduler import (
    generate_monthly_schedule_preview,
    save_monthly_schedule,
)

from apps.api.views.utils import _not_modified_or_response
from apps.api.permissions import IsMemberUser


def _group_monthly_schedule_qs(schedules):
    grouped = defaultdict(lambda: {"time": None, "items": []})

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
    permission_classes = [IsMemberUser]

    @staticmethod
    def get(request):
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

    def post(self, request):
        year = request.data.get("year")
        month = request.data.get("month")
        fixed_list = request.data.get("fixed", []) or []

        fixed_map = {}
        for f in fixed_list:
            try:
                schedule_type_id = int(f["schedule_type_id"])
                d = date.fromisoformat(f["date"])
                member_id = int(f["member_id"])
            except Exception:
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

    def post(self, request):
        try:
            year = int(request.data["year"])
            month = int(request.data["month"])
            items = request.data.get("items", []) or []

            normalized = []
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
                except Exception:
                    continue

            # DEBUG TEMPORÁRIO — remove depois que resolver
            print("=== SAVE DEBUG ===")
            print(f"year={year}, month={month}")
            for item in normalized:
                print(item)
            print("==================")

            save_monthly_schedule(year=year, month=month, items=normalized)
            return Response({"ok": True}, status=200)
        
        except ValueError as e:
            # Captura erros de validação específicos (como o de sobrescrever escala recente)
            return Response({"error": str(e)}, status=400)
        
        except Exception as e:
            # Captura outros erros genéricos
            return Response({"error": "Erro interno ao salvar escala: " + str(e)}, status=500)