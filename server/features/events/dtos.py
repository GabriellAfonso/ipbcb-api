"""Data carried between the events layers (specs/020-church-events/data-model.md)."""

from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel, field_validator

from core.application.dtos.strict_base import StrictBaseModel
from features.events.domain.event_enums import EventVisibility


class EventAuthorDTO(BaseModel):
    """Who created or last edited an event, as the panel shows it. ``name`` is the profile
    name, maybe ""."""

    id: UUID
    name: str


class EventRecordDTO(BaseModel):
    """An event as stored. The public resource is this without the audit fields."""

    id: int
    title: str
    start_date: date
    end_date: date | None
    start_time: time | None
    location: str | None
    description: str | None
    image_path: str
    visibility: EventVisibility
    created_by: EventAuthorDTO | None
    updated_by: EventAuthorDTO | None
    created_at: datetime
    updated_at: datetime


def _blank_to_none(value: str | None) -> str | None:
    """Trimmed text, or None when nothing is left — the app reads null, never ""."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _required_title(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"Title must not be blank; got {value!r}.")
    return stripped


class EventCreateDTO(StrictBaseModel):
    """A new event's fields. The image travels beside it, as a stream.

    >>> EventCreateDTO(title=" Retiro ", start_date=date(2026, 11, 14), location="  ").location
    """

    title: str
    start_date: date
    end_date: date | None = None
    start_time: time | None = None
    location: str | None = None
    description: str | None = None
    visibility: EventVisibility = EventVisibility.PUBLIC

    _title = field_validator("title")(_required_title)
    _optional_text = field_validator("location", "description")(_blank_to_none)


class EventPatchDTO(StrictBaseModel):
    """Partial edit. Only ``model_fields_set`` is applied: an absent field is left alone, a field
    sent as None is cleared. ``title``, ``start_date`` and ``visibility`` cannot be cleared —
    the serializer refuses null for them.

    >>> EventPatchDTO(end_date=None).model_fields_set
    {'end_date'}
    """

    title: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    start_time: time | None = None
    location: str | None = None
    description: str | None = None
    visibility: EventVisibility | None = None

    _optional_text = field_validator("location", "description")(_blank_to_none)

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, value: str | None) -> str | None:
        return None if value is None else _required_title(value)

    def resulting_dates(self, start_date: date, end_date: date | None) -> tuple[date, date | None]:
        """Start and end the event will have once this patch is applied to ``start_date`` and
        ``end_date``.

        >>> EventPatchDTO(end_date=None).resulting_dates(date(2026, 11, 14), date(2026, 11, 16))
        (datetime.date(2026, 11, 14), None)
        """
        sent = self.model_fields_set
        new_start = self.start_date if "start_date" in sent and self.start_date else start_date
        new_end = self.end_date if "end_date" in sent else end_date
        return new_start, new_end

    def changes(self) -> dict[str, object]:
        """Only the fields the caller sent, ready to apply.

        >>> EventPatchDTO(location=" ").changes()
        {'location': None}
        """
        return {name: getattr(self, name) for name in self.model_fields_set}
