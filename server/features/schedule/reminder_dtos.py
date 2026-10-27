"""DTOs of the rota reminders (specs/024-schedule-reminders)."""

import datetime
from enum import StrEnum

from pydantic import ConfigDict

from core.application.dtos.strict_base import StrictBaseModel


class ReminderKind(StrEnum):
    """The value is both the push ``type`` and the stored claim ``kind``."""

    WEEK = "schedule_week"
    EVE = "schedule_eve"
    PUBLISHED = "schedule_published"


class RotaEntryDTO(StrictBaseModel):
    """One rota entry as the reminders need it. ``month_first_saved_at`` is the earliest save of
    its month: the overwrite window, and so the publication moment, is measured from it.

    Annotations are module-qualified: a field named ``date`` would shadow the type.
    """

    date: datetime.date
    member_id: int
    service_id: int
    service_name: str
    start_time: datetime.time
    month_first_saved_at: datetime.datetime
    # "M", "F" or None: the member's own gender, for the wording of their reminder (FR-020).
    member_gender: str | None = None


class RotaSlot(StrictBaseModel):
    """One slot on the wire: ``{"date": "2026-10-29", "service": "...", "time": "19:30"}``."""

    date: str
    service: str
    time: str


class ReminderClaimKey(StrictBaseModel):
    """Who and which occasion one claim is for. Frozen so it can key a dict."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    member_id: int
    occasion: str


class KindRunReport(StrictBaseModel):
    """What one run did for one reminder kind whose window was open."""

    kind: ReminderKind
    occasions: list[str] = []
    claimed: int = 0
    devices: int = 0
    sent: int = 0


class ScheduleReminderRunReport(StrictBaseModel):
    """What one ``send_schedule_reminders`` run did; one entry per open window."""

    kinds: list[KindRunReport] = []
