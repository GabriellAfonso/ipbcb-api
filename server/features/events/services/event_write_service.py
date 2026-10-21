from typing import IO
from uuid import UUID

from core.domain.exceptions import EventImageMissingError, EventNotFoundError
from features.events.domain.event_dates import ensure_dates_ordered
from features.events.dtos import EventCreateDTO, EventPatchDTO, EventRecordDTO
from features.events.repositories.interfaces import EventImageStorage, EventRepository
from features.events.services.event_image_preparer import EventImagePreparer


class EventWriteService:
    """Creates, edits and deletes events from the panel (specs/020-church-events).

    The image file is written before the row and removed again if the row write fails, so a
    failed request leaves no orphan file; a replaced or deleted event's old file is removed only
    after the row change succeeded.
    """

    def __init__(
        self,
        repository: EventRepository,
        image_storage: EventImageStorage,
        image_preparer: EventImagePreparer,
    ) -> None:
        self._repository = repository
        self._storage = image_storage
        self._preparer = image_preparer

    def create_event(
        self, event: EventCreateDTO, image: IO[bytes] | None, creator_id: UUID
    ) -> EventRecordDTO:
        """Store the image, then the event.

        >>> service.create_event(EventCreateDTO(title="Retiro", start_date=d), poster, user_id).id
        12
        """
        if image is None:
            raise EventImageMissingError()
        ensure_dates_ordered(event.start_date, event.end_date)
        image_path = self._storage.save(self._preparer.prepare(image))
        try:
            return self._repository.create(event, image_path, creator_id)
        except Exception:
            self._storage.delete(image_path)
            raise

    def update_event(
        self, event_id: int, patch: EventPatchDTO, image: IO[bytes] | None
    ) -> EventRecordDTO:
        """Apply the sent fields and, when given, a new image; the old image file goes after.

        >>> service.update_event(12, EventPatchDTO(location="Templo"), None).location
        'Templo'
        """
        current = self._existing(event_id)
        # Checked on the event as it will be, not on the sent fields alone (FR-004).
        ensure_dates_ordered(*patch.resulting_dates(current.start_date, current.end_date))
        changes = patch.changes()
        if image is None:
            return self._repository.update(event_id, changes, None)
        return self._update_with_image(current, changes, image)

    def delete_event(self, event_id: int) -> None:
        """Remove the event for good, then its image file.

        >>> service.delete_event(12)
        """
        current = self._existing(event_id)
        self._repository.delete(event_id)
        self._storage.delete(current.image_path)

    def _update_with_image(
        self, current: EventRecordDTO, changes: dict[str, object], image: IO[bytes]
    ) -> EventRecordDTO:
        new_path = self._storage.save(self._preparer.prepare(image))
        try:
            updated = self._repository.update(current.id, changes, new_path)
        except Exception:
            self._storage.delete(new_path)
            raise
        self._storage.delete(current.image_path)
        return updated

    def _existing(self, event_id: int) -> EventRecordDTO:
        current = self._repository.get(event_id)
        if current is None:
            raise EventNotFoundError(event_id)
        return current
