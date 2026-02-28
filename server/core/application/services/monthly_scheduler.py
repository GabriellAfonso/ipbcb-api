import random
import calendar
from collections import defaultdict
from django.utils import timezone
from datetime import date, datetime, timedelta
from django.db import transaction

from apps.persistence.models.schedule import (
    ScheduleType,
    MemberScheduleConfig,
    MonthlySchedule,
)


WEEKDAYS_MAP = {
    1: calendar.SUNDAY,
    3: calendar.TUESDAY,
    5: calendar.THURSDAY,
}


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


def generate_monthly_schedule_preview(
    year: int | None = None,
    month: int | None = None,
    fixed: dict[tuple[int, date], int] | None = None,
) -> dict:
    """
    Generates a schedule preview (does NOT write to DB).

    fixed:
      dict with key (schedule_type_id, date_obj) -> member_id
      Example: {(3, date(2026, 3, 2)): 10}
    """
    if year is None or month is None:
        year, month = _next_month_from(date.today())

    fixed = fixed or {}

    suggested: list[dict] = []
    used_member_ids: set[int] = set()

    # uso global no mês (por membro, atravessando todos os tipos)
    usage_count: dict[int, int] = defaultdict(int)

    schedule_types = list(ScheduleType.objects.all())

    for schedule_type in schedule_types:
        if schedule_type.weekday not in WEEKDAYS_MAP:
            continue

        target_weekday = WEEKDAYS_MAP[schedule_type.weekday]
        dates = _month_dates_for_weekday(year, month, target_weekday)

        configs = list(
            MemberScheduleConfig.objects.filter(
                schedule_type=schedule_type,
                available=True,
            ).select_related("member")
        )
        if not configs:
            continue

        allowed_member_by_id = {cfg.member_id: cfg.member for cfg in configs}

        # pool ponderado por weight (múltiplas entradas do mesmo membro)
        weighted_members = []
        for cfg in configs:
            weighted_members.extend([cfg.member] * max(int(cfg.weight), 1))

        random.shuffle(weighted_members)

        for d in dates:
            # 1) Apply fixed first (if valid for this schedule_type)
            fixed_member_id = fixed.get((schedule_type.id, d))
            if fixed_member_id:
                member = allowed_member_by_id.get(fixed_member_id)
                if member:
                    usage_count[member.id] += 1
                    used_member_ids.add(member.id)

                    data = {
                        "date": d.isoformat(),
                        "day": d.day,
                        "schedule_type": {
                            "id": schedule_type.id,
                            "name": schedule_type.name,
                            "time": schedule_type.time.strftime("%H:%M"),
                        },
                        "member": {"id": member.id, "name": member.name},
                        "fixed": True,
                    }
                    suggested.append(data)
                    continue
                # fixed inválido -> cai na geração normal

            # 2) Normal generation: pick someone from pool (avoid overusing)
            # remove members already used in month if possible (soft rule)
            candidates = [
                m for m in weighted_members if m.id not in used_member_ids]
            if not candidates:
                candidates = list(weighted_members)

            if not candidates:
                # nada pra escolher
                continue

            # prefer members never used this month; else pick least used
            unused = [m for m in candidates if usage_count[m.id] == 0]
            if unused:
                member = random.choice(unused)
            else:
                min_usage = min(usage_count[m.id] for m in candidates)
                least_used = [
                    m for m in candidates if usage_count[m.id] == min_usage]
                member = random.choice(least_used)

            usage_count[member.id] += 1
            used_member_ids.add(member.id)

            # tenta remover UMA ocorrência do membro do pool (pra espalhar)
            try:
                weighted_members.remove(member)
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
                    "member": {"id": member.id, "name": member.name},
                    "fixed": False,
                }
            )

    suggested.sort(key=lambda x: (x["schedule_type"]["name"], x["date"]))
    return {"year": year, "month": month, "items": suggested}

def save_monthly_schedule(year: int, month: int, items: list[dict]) -> None:
    with transaction.atomic():
        # Busca o registro mais antigo para validar o tempo de criação
        existing_first = MonthlySchedule.objects.filter(year=year, month=month).order_by("created_at").first()

        if existing_first:
            # Verifica se já passaram 30 minutos desde a criação
            if timezone.now() > existing_first.created_at + timedelta(minutes=30):
                raise ValueError(
                    f"A escala de {month:02d}/{year} foi criada há mais de 30 minutos. "
                    "Por segurança, não é mais possível sobrescrevê-la."
                )
            
            # Remove os registros existentes para a nova escrita
            MonthlySchedule.objects.filter(year=year, month=month).delete()

        to_create = []
        for it in items:
            d = date.fromisoformat(it["date"])
            
            to_create.append(
                MonthlySchedule(
                    date=d,
                    year=d.year,
                    month=d.month,
                    schedule_type_id=int(it["schedule_type_id"]),
                    member_id=int(it["member_id"]),
                )
            )

        MonthlySchedule.objects.bulk_create(to_create)

# Backward-compatible name (now returns preview, does NOT write to DB)
def generate_monthly_schedule():
    return generate_monthly_schedule_preview()
