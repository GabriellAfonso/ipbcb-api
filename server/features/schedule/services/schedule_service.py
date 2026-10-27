import random
import calendar
from collections import defaultdict
from datetime import date
from typing import Any

from django.utils import timezone

from core.domain.exceptions import ScheduleOverwriteError
from core.domain.weekday import to_python_weekday
from core.metrics import SCHEDULE_GENERATED_COUNTER, SCHEDULE_SAVED_COUNTER
from features.schedule.dtos import MonthlyScheduleDTO
from features.schedule.repositories.interfaces import ScheduleRepository
from features.schedule.services.reminder_rules import OVERWRITE_WINDOW

# There used to be a WEEKDAYS_MAP here covering only Sunday, Tuesday and Thursday, and
# any service on another weekday was skipped with no error and no rows. It worked only
# because the church's three services happened to fall on those days. Replaced by the
# shared conversion in core/domain/weekday.py, so every weekday now generates.


def _next_month_from(today: date) -> tuple[int, int]:
    if today.month == 12:
        return today.year + 1, 1
    return today.year, today.month + 1


def _month_dates_for_weekday(year: int, month: int, target_weekday: int) -> list[date]:
    _, last_day = calendar.monthrange(year, month)
    return [
        date(year, month, day)
        for day in range(1, last_day + 1)
        if date(year, month, day).weekday() == target_weekday
    ]


def _group_schedules(schedules: list[MonthlyScheduleDTO]) -> dict[str, Any]:
    grouped: dict[str, Any] = defaultdict(lambda: {"time": None, "items": []})

    for s in schedules:
        key = s.schedule_type_name
        grouped[key]["time"] = s.schedule_type_time.strftime("%H:%M")
        grouped[key]["items"].append(
            {
                "date": s.date.isoformat(),
                "day": s.date.day,
                "member": {"id": s.member_id, "name": s.member_name},
                "schedule_type": {"id": s.schedule_type_id, "name": s.schedule_type_name},
            }
        )

    return grouped


class ScheduleService:
    def __init__(self, repository: ScheduleRepository) -> None:
        self._repository = repository

    def get_current_month_schedule(self, today: date) -> dict[str, Any]:
        schedules = self._repository.list_monthly_schedules(today.year, today.month)
        return {
            "year": today.year,
            "month": today.month,
            "schedule": _group_schedules(schedules),
        }

    def generate_preview(
        self,
        year: int | None = None,
        month: int | None = None,
        fixed: dict[tuple[int, date], int] | None = None,
    ) -> dict[str, Any]:
        """
        Generates a schedule preview (does NOT write to DB).

        fixed:
          dict with key (schedule_type_id, date_obj) -> member_id
          Example: {(3, date(2026, 3, 2)): 10}
        """
        if year is None or month is None:
            year, month = _next_month_from(date.today())

        fixed = fixed or {}

        suggested: list[dict[str, Any]] = []
        used_member_ids: set[int] = set()

        # uso global no mês (por membro, atravessando todos os tipos)
        usage_count: dict[int, int] = defaultdict(int)

        schedule_types = self._repository.list_schedule_types()

        for schedule_type in schedule_types:
            # Escola Bíblica Dominical is held but nobody is rostered for it. This is
            # the only intentional skip — an unschedulable service must never vanish
            # silently the way the old weekday map made it.
            if not schedule_type.takes_rota:
                continue

            target_weekday = to_python_weekday(schedule_type.weekday)
            dates = _month_dates_for_weekday(year, month, target_weekday)

            configs = self._repository.list_available_configs(schedule_type.id)
            if not configs:
                continue

            allowed_member_by_id = {cfg.member_id: cfg for cfg in configs}

            weighted_members: list[int] = []
            for cfg in configs:
                weighted_members.extend([cfg.member_id] * max(int(cfg.weight), 1))

            random.shuffle(weighted_members)

            member_name_by_id = {cfg.member_id: cfg.member_name for cfg in configs}

            for d in dates:
                fixed_member_id = fixed.get((schedule_type.id, d))
                if fixed_member_id:
                    fixed_cfg = allowed_member_by_id.get(fixed_member_id)
                    if fixed_cfg:
                        usage_count[fixed_cfg.member_id] += 1
                        used_member_ids.add(fixed_cfg.member_id)

                        data: dict[str, Any] = {
                            "date": d.isoformat(),
                            "day": d.day,
                            "schedule_type": {
                                "id": schedule_type.id,
                                "name": schedule_type.name,
                                "time": schedule_type.time.strftime("%H:%M"),
                            },
                            "member": {"id": fixed_cfg.member_id, "name": fixed_cfg.member_name},
                            "fixed": True,
                        }
                        suggested.append(data)
                        continue

                candidates = [m for m in weighted_members if m not in used_member_ids]
                if not candidates:
                    candidates = list(weighted_members)

                if not candidates:
                    continue

                unused = [m for m in candidates if usage_count[m] == 0]
                if unused:
                    member_id = random.choice(unused)  # nosec B311
                else:
                    min_usage = min(usage_count[m] for m in candidates)
                    least_used = [m for m in candidates if usage_count[m] == min_usage]
                    member_id = random.choice(least_used)  # nosec B311

                usage_count[member_id] += 1
                used_member_ids.add(member_id)

                try:
                    weighted_members.remove(member_id)
                except ValueError:
                    pass

                suggested.append(
                    {
                        "date": d.isoformat(),
                        "day": d.day,
                        "schedule_type": {
                            "id": schedule_type.id,
                            "name": schedule_type.name,
                            "time": schedule_type.time.strftime("%H:%M"),
                        },
                        "member": {"id": member_id, "name": member_name_by_id[member_id]},
                        "fixed": False,
                    }
                )

        suggested.sort(key=lambda x: (x["schedule_type"]["name"], x["date"]))
        SCHEDULE_GENERATED_COUNTER.inc()
        return {"year": year, "month": month, "items": suggested}

    def save_schedule(self, year: int, month: int, items: list[dict[str, Any]]) -> None:
        earliest = self._repository.get_earliest_created_at(year, month)

        if earliest:
            if timezone.now() > earliest + OVERWRITE_WINDOW:
                raise ScheduleOverwriteError(month, year)

        self._repository.replace_schedules(year, month, items)
        SCHEDULE_SAVED_COUNTER.inc()
