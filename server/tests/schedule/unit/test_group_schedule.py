from __future__ import annotations

from datetime import date, time
from unittest.mock import MagicMock

from features.schedule.views.schedule import _group_monthly_schedule_qs


def _make_schedule_obj(
    type_name: str, type_time: time, d: date, member_id: int, member_name: str
) -> MagicMock:
    schedule_type = MagicMock()
    schedule_type.name = type_name
    schedule_type.time = type_time
    schedule_type.id = 1

    member = MagicMock()
    member.name = member_name
    member.id = member_id

    obj = MagicMock()
    obj.schedule_type = schedule_type
    obj.schedule_type_id = schedule_type.id
    obj.member = member
    obj.member_id = member_id
    obj.date = d
    return obj


class TestGroupMonthlyScheduleQs:
    def test_groups_by_schedule_type_name(self) -> None:
        s1 = _make_schedule_obj("Culto", time(9, 0), date(2026, 5, 3), 1, "Alice")
        s2 = _make_schedule_obj("Culto", time(9, 0), date(2026, 5, 10), 2, "Bob")
        s3 = _make_schedule_obj("EBD", time(10, 0), date(2026, 5, 3), 3, "Carol")

        result = _group_monthly_schedule_qs([s1, s2, s3])  # type: ignore[arg-type]

        assert "Culto" in result
        assert "EBD" in result
        assert len(result["Culto"]["items"]) == 2
        assert len(result["EBD"]["items"]) == 1

    def test_time_formatted_as_hh_mm(self) -> None:
        s = _make_schedule_obj("Culto", time(9, 0), date(2026, 5, 3), 1, "Alice")

        result = _group_monthly_schedule_qs([s])  # type: ignore[arg-type]

        assert result["Culto"]["time"] == "09:00"

    def test_item_structure(self) -> None:
        s = _make_schedule_obj("Culto", time(9, 0), date(2026, 5, 3), 1, "Alice")

        result = _group_monthly_schedule_qs([s])  # type: ignore[arg-type]
        item = result["Culto"]["items"][0]

        assert item["date"] == "2026-05-03"
        assert item["day"] == 3
        assert item["member"] == {"id": 1, "name": "Alice"}
        assert item["schedule_type"]["name"] == "Culto"

    def test_empty_queryset_returns_empty_dict(self) -> None:
        result = _group_monthly_schedule_qs([])  # type: ignore[arg-type]
        assert dict(result) == {}
