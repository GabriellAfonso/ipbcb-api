from collections.abc import Mapping
from datetime import date
from uuid import UUID

from django.db.models import F, Q, QuerySet

from core.domain.exceptions import EventNotFoundError
from features.events.domain.event_enums import EventStatusFilter, EventVisibility
from features.events.dtos import EventCreateDTO, EventCreatorDTO, EventRecordDTO
from features.events.models.event import Event

# Public order: soonest first; an all-day event (no time) before timed ones on the same date.
_PUBLIC_ORDER = ("start_date", F("start_time").asc(nulls_first=True), "id")
_MANAGEMENT_ORDER = ("-start_date", F("start_time").desc(nulls_last=True), "-id")


def _with_creator() -> QuerySet[Event]:
    # The creator's profile name is shown to the panel; joined so a list is one query.
    return Event.objects.select_related("created_by__profile")


def _still_active(today: date) -> Q:
    """Last day (end date, else start date) is ``today`` or later — COALESCE spelled as two
    branches, so each can use its column."""
    return Q(end_date__gte=today) | Q(end_date__isnull=True, start_date__gte=today)


def _active(today: date, include_members: bool) -> QuerySet[Event]:
    events = _with_creator().filter(_still_active(today))
    if include_members:
        return events
    return events.filter(visibility=EventVisibility.PUBLIC.value)


class EventRepositoryImpl:
    """ORM persistence of events (specs/020-church-events/data-model.md).

    >>> EventRepositoryImpl().list_active(date(2026, 11, 14), include_members=False)
    [EventRecordDTO(...)]
    """

    def list_active(self, today: date, include_members: bool) -> list[EventRecordDTO]:
        events = _active(today, include_members).order_by(*_PUBLIC_ORDER)
        return [_to_record(event) for event in events]

    def get_active(
        self, event_id: int, today: date, include_members: bool
    ) -> EventRecordDTO | None:
        event = _active(today, include_members).filter(pk=event_id).first()
        return _to_record(event) if event else None

    def list_all(self, status: EventStatusFilter, today: date) -> list[EventRecordDTO]:
        events = _with_creator()
        if status is EventStatusFilter.ACTIVE:
            events = events.filter(_still_active(today))
        elif status is EventStatusFilter.PAST:
            events = events.exclude(_still_active(today))
        return [_to_record(event) for event in events.order_by(*_MANAGEMENT_ORDER)]

    def get(self, event_id: int) -> EventRecordDTO | None:
        event = _with_creator().filter(pk=event_id).first()
        return _to_record(event) if event else None

    def create(self, event: EventCreateDTO, image_path: str, creator_id: UUID) -> EventRecordDTO:
        created = Event.objects.create(
            **event.model_dump(), image_path=image_path, created_by_id=creator_id
        )
        return self._reloaded(created.pk)

    def update(
        self, event_id: int, changes: Mapping[str, object], image_path: str | None
    ) -> EventRecordDTO:
        event = Event.objects.filter(pk=event_id).first()
        if event is None:
            raise EventNotFoundError(event_id)
        for field_name, value in changes.items():
            setattr(event, field_name, value)
        if image_path is not None:
            event.image_path = image_path
        event.save()
        return self._reloaded(event_id)

    def delete(self, event_id: int) -> None:
        Event.objects.filter(pk=event_id).delete()

    def _reloaded(self, event_id: int) -> EventRecordDTO:
        # Read back with the creator joined, so the answer has the same shape as a read.
        record = self.get(event_id)
        if record is None:
            raise EventNotFoundError(event_id)
        return record


def _to_record(event: Event) -> EventRecordDTO:
    return EventRecordDTO(
        id=event.pk,
        title=event.title,
        start_date=event.start_date,
        end_date=event.end_date,
        start_time=event.start_time,
        location=event.location,
        description=event.description,
        image_path=event.image_path,
        visibility=EventVisibility(event.visibility),
        created_by=_creator_of(event),
        created_at=event.created_at,
        updated_at=event.updated_at,
    )


def _creator_of(event: Event) -> EventCreatorDTO | None:
    creator = event.created_by
    if creator is None:
        return None
    # A user without a profile row has no name to show, not an error.
    profile = getattr(creator, "profile", None)
    return EventCreatorDTO(id=creator.pk, name=getattr(profile, "name", "") or "")
