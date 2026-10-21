from collections.abc import Mapping
from datetime import date
from uuid import UUID

from django.contrib.auth.base_user import AbstractBaseUser
from django.db.models import F, Q, QuerySet

from core.domain.exceptions import EventNotFoundError
from features.events.domain.event_enums import EventStatusFilter, EventVisibility
from features.events.dtos import EventAuthorDTO, EventCreateDTO, EventRecordDTO
from features.events.models.event import Event

# Public order: soonest first; an all-day event (no time) before timed ones on the same date.
_PUBLIC_ORDER = ("start_date", F("start_time").asc(nulls_first=True), "id")
_MANAGEMENT_ORDER = ("-start_date", F("start_time").desc(nulls_last=True), "-id")


def _with_authors() -> QuerySet[Event]:
    # The creator's and last editor's profile names are shown to the panel; joined so a list is
    # one query.
    return Event.objects.select_related("created_by__profile", "updated_by__profile")


def _still_active(today: date) -> Q:
    """Last day (end date, else start date) is ``today`` or later — COALESCE spelled as two
    branches, so each can use its column."""
    return Q(end_date__gte=today) | Q(end_date__isnull=True, start_date__gte=today)


def _active(today: date, include_members: bool) -> QuerySet[Event]:
    events = _with_authors().filter(_still_active(today))
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
        events = _with_authors()
        if status is EventStatusFilter.ACTIVE:
            events = events.filter(_still_active(today))
        elif status is EventStatusFilter.PAST:
            events = events.exclude(_still_active(today))
        return [_to_record(event) for event in events.order_by(*_MANAGEMENT_ORDER)]

    def get(self, event_id: int) -> EventRecordDTO | None:
        event = _with_authors().filter(pk=event_id).first()
        return _to_record(event) if event else None

    def create(self, event: EventCreateDTO, image_path: str, creator_id: UUID) -> EventRecordDTO:
        created = Event.objects.create(
            **event.model_dump(), image_path=image_path, created_by_id=creator_id
        )
        return self._reloaded(created.pk)

    def update(
        self,
        event_id: int,
        changes: Mapping[str, object],
        image_path: str | None,
        editor_id: UUID,
    ) -> EventRecordDTO:
        event = Event.objects.filter(pk=event_id).first()
        if event is None:
            raise EventNotFoundError(event_id)
        for field_name, value in changes.items():
            setattr(event, field_name, value)
        if image_path is not None:
            event.image_path = image_path
        event.updated_by_id = editor_id
        event.save()
        return self._reloaded(event_id)

    def delete(self, event_id: int) -> None:
        Event.objects.filter(pk=event_id).delete()

    def _reloaded(self, event_id: int) -> EventRecordDTO:
        # Read back with the authors joined, so the answer has the same shape as a read.
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
        created_by=_author_of(event.created_by),
        updated_by=_author_of(event.updated_by),
        created_at=event.created_at,
        updated_at=event.updated_at,
    )


def _author_of(user: AbstractBaseUser | None) -> EventAuthorDTO | None:
    if user is None:
        return None
    # A user without a profile row has no name to show, not an error.
    profile = getattr(user, "profile", None)
    return EventAuthorDTO(id=user.pk, name=getattr(profile, "name", "") or "")
