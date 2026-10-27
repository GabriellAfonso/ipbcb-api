from collections.abc import Collection
from datetime import date, datetime
from typing import Any, Protocol
from uuid import UUID

from features.schedule.dtos import MemberConfigDTO, MonthlyScheduleDTO, ScheduleTypeDTO
from features.schedule.reminder_dtos import ReminderClaimKey, ReminderKind, RotaEntryDTO


class ScheduleRepository(Protocol):
    """Contract for schedule persistence operations."""

    def list_schedule_types(self) -> list[ScheduleTypeDTO]: ...

    def list_available_configs(self, schedule_type_id: int) -> list[MemberConfigDTO]: ...

    def list_monthly_schedules(self, year: int, month: int) -> list[MonthlyScheduleDTO]: ...

    def get_earliest_created_at(self, year: int, month: int) -> datetime | None: ...

    def replace_schedules(self, year: int, month: int, items: list[dict[str, Any]]) -> None: ...


class RotaReminderRepository(Protocol):
    """Contract for the rota reminder reads and claims (specs/024-schedule-reminders)."""

    def entries_between(self, first: date, last: date) -> list[RotaEntryDTO]: ...

    def entries_of_months_from(
        self, months: Collection[tuple[int, int]], first: date
    ) -> list[RotaEntryDTO]: ...

    def months_first_saved_between(
        self, since: datetime, until: datetime
    ) -> list[tuple[int, int]]: ...

    def claim(
        self, kind: ReminderKind, keys: Collection[ReminderClaimKey], run_id: UUID
    ) -> set[ReminderClaimKey]: ...
