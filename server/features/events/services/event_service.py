from datetime import date

from core.domain.exceptions import EventNotFoundError
from core.time.clock import Clock
from features.events.domain.event_dates import today_in_events_zone
from features.events.domain.event_enums import parse_status_filter
from features.events.dtos import EventRecordDTO
from features.events.repositories.interfaces import EventImageStorage, EventRepository


class EventService:
    """Reads of events: the public carousel and detail, and the panel's list and detail.

    "Today" comes from the injected clock in São Paulo time, so an event leaves the public list
    on the first request after its last day with nothing scheduled (specs/020-church-events).
    """

    def __init__(
        self, repository: EventRepository, image_storage: EventImageStorage, clock: Clock
    ) -> None:
        self._repository = repository
        self._storage = image_storage
        self._clock = clock

    def list_visible(self, include_members: bool) -> list[EventRecordDTO]:
        """Active events the caller may see, soonest first.

        >>> service.list_visible(include_members=False)
        [EventRecordDTO(title='Congresso de Jovens', ...)]
        """
        return self._repository.list_active(self._today(), include_members)

    def get_visible(self, event_id: int, include_members: bool) -> EventRecordDTO:
        """One active event the caller may see. Past, hidden and missing look the same.

        >>> service.get_visible(12, include_members=True).title
        'Congresso de Jovens'
        """
        record = self._repository.get_active(event_id, self._today(), include_members)
        if record is None:
            raise EventNotFoundError(event_id)
        return record

    def list_for_management(self, status_raw: str | None) -> list[EventRecordDTO]:
        """Every event matching the ``status`` filter (``all`` when absent), newest first.

        >>> service.list_for_management("past")
        [EventRecordDTO(...)]
        """
        status = parse_status_filter(status_raw)
        return self._repository.list_all(status, self._today())

    def get_for_management(self, event_id: int) -> EventRecordDTO:
        """One event whatever its state or visibility.

        >>> service.get_for_management(12).visibility
        <EventVisibility.MEMBERS: 'members'>
        """
        record = self._repository.get(event_id)
        if record is None:
            raise EventNotFoundError(event_id)
        return record

    def image_url_path(self, image_path: str) -> str:
        """URL path the app loads an event image from, through the media access check.

        >>> service.image_url_path("events/8c41....jpg")
        '/ipbcb/media/events/8c41....jpg'
        """
        return self._storage.url(image_path)

    def _today(self) -> date:
        return today_in_events_zone(self._clock.now())
