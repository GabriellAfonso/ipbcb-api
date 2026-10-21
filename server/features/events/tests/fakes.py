"""Named in-memory fakes for the events feature's ports (CLAUDE.md §10)."""

from collections.abc import Mapping
from datetime import date, datetime, timezone
from itertools import count
from typing import IO
from uuid import UUID

from core.domain.exceptions import EventNotFoundError, ImageProcessingError
from features.events.domain.event_dates import last_day
from features.events.domain.event_enums import EventStatusFilter, EventVisibility
from features.events.dtos import EventCreateDTO, EventCreatorDTO, EventRecordDTO

CREATED_AT = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)


class FixedClock:
    """A clock stopped at ``now``; tests move it by assigning ``now``."""

    def __init__(self, now: datetime) -> None:
        self.now_value = now

    def now(self) -> datetime:
        return self.now_value


class FakeEventRepository:
    """Events as ``EventRecordDTO`` in a dict, filtered and ordered like the real repository."""

    def __init__(self) -> None:
        self.records: dict[int, EventRecordDTO] = {}
        self.fail_next_write = False
        self._ids = count(1)

    def add(self, **fields: object) -> EventRecordDTO:
        """Seed a record; unspecified fields get harmless defaults."""
        event_id = next(self._ids)
        defaults: dict[str, object] = {
            "id": event_id,
            "title": f"Evento {event_id}",
            "start_date": date(2026, 11, 14),
            "end_date": None,
            "start_time": None,
            "location": None,
            "description": None,
            "image_path": f"events/{event_id}.jpg",
            "visibility": EventVisibility.PUBLIC,
            "created_by": None,
            "created_at": CREATED_AT,
            "updated_at": CREATED_AT,
        }
        record = EventRecordDTO.model_validate({**defaults, **fields})
        self.records[record.id] = record
        return record

    def list_active(self, today: date, include_members: bool) -> list[EventRecordDTO]:
        active = [r for r in self.records.values() if _visible(r, today, include_members)]
        return sorted(active, key=_public_key)

    def get_active(
        self, event_id: int, today: date, include_members: bool
    ) -> EventRecordDTO | None:
        record = self.records.get(event_id)
        return record if record and _visible(record, today, include_members) else None

    def list_all(self, status: EventStatusFilter, today: date) -> list[EventRecordDTO]:
        matching = [r for r in self.records.values() if _matches(r, status, today)]
        return sorted(matching, key=_public_key, reverse=True)

    def get(self, event_id: int) -> EventRecordDTO | None:
        return self.records.get(event_id)

    def create(self, event: EventCreateDTO, image_path: str, creator_id: UUID) -> EventRecordDTO:
        self._maybe_fail()
        creator = EventCreatorDTO(id=creator_id, name="Criador")
        return self.add(**event.model_dump(), image_path=image_path, created_by=creator)

    def update(
        self, event_id: int, changes: Mapping[str, object], image_path: str | None
    ) -> EventRecordDTO:
        self._maybe_fail()
        current = self.records.get(event_id)
        if current is None:
            raise EventNotFoundError(event_id)
        image = {"image_path": image_path} if image_path else {}
        updated = current.model_copy(update={**changes, **image})
        self.records[event_id] = updated
        return updated

    def delete(self, event_id: int) -> None:
        self.records.pop(event_id, None)

    def _maybe_fail(self) -> None:
        if self.fail_next_write:
            self.fail_next_write = False
            raise RuntimeError("database write failed")


def _visible(record: EventRecordDTO, today: date, include_members: bool) -> bool:
    if last_day(record.start_date, record.end_date) < today:
        return False
    return include_members or record.visibility is EventVisibility.PUBLIC


def _matches(record: EventRecordDTO, status: EventStatusFilter, today: date) -> bool:
    active = last_day(record.start_date, record.end_date) >= today
    if status is EventStatusFilter.ACTIVE:
        return active
    if status is EventStatusFilter.PAST:
        return not active
    return True


def _public_key(record: EventRecordDTO) -> tuple[date, int, str, int]:
    # No time sorts before any time, as in the real ascending order.
    has_time = 0 if record.start_time is None else 1
    return record.start_date, has_time, str(record.start_time or ""), record.id


class FakeEventImageStorage:
    """In-memory files with predictable names (``events/{n}.jpg``)."""

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.deleted: list[str] = []
        self._ids = count(1)

    def save(self, content: bytes) -> str:
        name = f"events/stored-{next(self._ids)}.jpg"
        self.files[name] = content
        return name

    def delete(self, name: str) -> None:
        self.deleted.append(name)
        self.files.pop(name, None)

    def url(self, name: str) -> str:
        return f"/media/{name}"


class FakeImageProcessor:
    """Reports a fixed displayed size and returns fixed JPEG bytes; can fail like a bad file."""

    FITTED = b"fitted-jpeg"

    def __init__(self, size: tuple[int, int] = (1920, 1080), fails: bool = False) -> None:
        self.size = size
        self.fails = fails
        self.fitted_calls: list[tuple[int, int, int]] = []

    def dimensions(self, source: IO[bytes]) -> tuple[int, int]:
        return self.size

    def upright_dimensions(self, source: IO[bytes]) -> tuple[int, int]:
        return self.size

    def fitted_jpeg(
        self, source: IO[bytes], max_width: int, max_height: int, quality: int
    ) -> bytes:
        if self.fails:
            raise ImageProcessingError("poster.png")
        self.fitted_calls.append((max_width, max_height, quality))
        return self.FITTED

    def bounded_jpeg(self, source: IO[bytes], longest_side: int, quality: int) -> bytes:
        raise AssertionError("Events never use bounded_jpeg.")

    def square_jpeg(self, source: IO[bytes], side: int, quality: int) -> bytes:
        raise AssertionError("Events never use square_jpeg.")

    def capture_date(self, source: IO[bytes]) -> date | None:
        raise AssertionError("Events never use capture_date.")
