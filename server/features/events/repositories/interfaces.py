from collections.abc import Mapping
from datetime import date
from typing import Protocol
from uuid import UUID

from features.events.domain.event_enums import EventStatusFilter
from features.events.dtos import EventCreateDTO, EventRecordDTO


class EventRepository(Protocol):
    """Persistence of events. The only layer that runs ORM queries for them."""

    def list_active(self, today: date, include_members: bool) -> list[EventRecordDTO]:
        """Events whose last day is ``today`` or later, in public order (start date, time with
        absent first, id). ``members`` events only when ``include_members``."""
        ...

    def get_active(
        self, event_id: int, today: date, include_members: bool
    ) -> EventRecordDTO | None:
        """One event under the same filter as ``list_active``, or None."""
        ...

    def list_all(self, status: EventStatusFilter, today: date) -> list[EventRecordDTO]:
        """Every event of both visibilities matching ``status``, newest start first (time with
        absent last, then id)."""
        ...

    def get(self, event_id: int) -> EventRecordDTO | None:
        """One event whatever its state or visibility, or None."""
        ...

    def create(self, event: EventCreateDTO, image_path: str, creator_id: UUID) -> EventRecordDTO:
        """Insert an event pointing at an already stored image."""
        ...

    def update(
        self, event_id: int, changes: Mapping[str, object], image_path: str | None
    ) -> EventRecordDTO:
        """Apply ``changes`` (field name → new value) and, when given, the new image path."""
        ...

    def delete(self, event_id: int) -> None:
        """Remove the row. The caller removes the image file."""
        ...


class EventImageStorage(Protocol):
    """Event image files, under ``events/`` with random names."""

    def save(self, content: bytes) -> str:
        """Store a JPEG and return its storage name, e.g. ``events/8c41….jpg``."""
        ...

    def delete(self, name: str) -> None:
        """Remove ``name``; a file already gone is not an error."""
        ...

    def url(self, name: str) -> str:
        """URL path of a stored file, e.g. ``/ipbcb/media/events/8c41….jpg``."""
        ...
