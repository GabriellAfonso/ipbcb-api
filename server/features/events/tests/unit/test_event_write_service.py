from datetime import date
from io import BytesIO
from uuid import uuid4

import pytest

from core.domain.exceptions import (
    EventDatesInvalidError,
    EventImageInvalidError,
    EventImageMissingError,
    EventNotFoundError,
)
from features.events.dtos import EventCreateDTO, EventPatchDTO
from features.events.services.event_image_preparer import EventImagePreparer
from features.events.services.event_write_service import EventWriteService
from features.events.tests.fakes import (
    FakeEventImageStorage,
    FakeEventRepository,
    FakeImageProcessor,
)
from features.events.tests.images import image_bytes

NOV_14 = date(2026, 11, 14)


class _Setup:
    def __init__(self, size: tuple[int, int] = (1920, 1080)) -> None:
        self.repo = FakeEventRepository()
        self.storage = FakeEventImageStorage()
        preparer = EventImagePreparer(FakeImageProcessor(size=size))
        self.service = EventWriteService(self.repo, self.storage, preparer)


def _poster() -> BytesIO:
    return BytesIO(image_bytes())


class TestCreate:
    def test_stores_the_image_then_the_event(self) -> None:
        setup = _Setup()
        creator = uuid4()

        record = setup.service.create_event(
            EventCreateDTO(title="Retiro", start_date=NOV_14), _poster(), creator
        )

        assert record.image_path in setup.storage.files
        assert record.created_by is not None and record.created_by.id == creator
        assert record.updated_by is None

    def test_without_image_is_refused(self) -> None:
        with pytest.raises(EventImageMissingError):
            _Setup().service.create_event(
                EventCreateDTO(title="Retiro", start_date=NOV_14), None, uuid4()
            )

    def test_end_before_start_is_refused_and_nothing_stored(self) -> None:
        setup = _Setup()
        dto = EventCreateDTO(title="Retiro", start_date=NOV_14, end_date=date(2026, 11, 13))

        with pytest.raises(EventDatesInvalidError):
            setup.service.create_event(dto, _poster(), uuid4())
        assert setup.storage.files == {}

    def test_invalid_image_stores_nothing(self) -> None:
        setup = _Setup(size=(1000, 1000))

        with pytest.raises(EventImageInvalidError):
            setup.service.create_event(
                EventCreateDTO(title="Retiro", start_date=NOV_14), _poster(), uuid4()
            )
        assert setup.storage.files == {} and setup.repo.records == {}

    def test_failed_row_write_removes_the_new_file(self) -> None:
        setup = _Setup()
        setup.repo.fail_next_write = True

        with pytest.raises(RuntimeError):
            setup.service.create_event(
                EventCreateDTO(title="Retiro", start_date=NOV_14), _poster(), uuid4()
            )
        assert setup.storage.files == {}


class TestUpdate:
    def test_only_sent_fields_change(self) -> None:
        setup = _Setup()
        event = setup.repo.add(location="Salão", description="Texto")

        updated = setup.service.update_event(
            event.id, EventPatchDTO(location="Templo"), None, uuid4()
        )

        assert updated.location == "Templo"
        assert updated.description == "Texto"
        assert updated.image_path == event.image_path

    def test_new_image_replaces_and_removes_the_old_file(self) -> None:
        setup = _Setup()
        event = setup.repo.add()

        updated = setup.service.update_event(event.id, EventPatchDTO(), _poster(), uuid4())

        assert updated.image_path != event.image_path
        assert setup.storage.deleted == [event.image_path]

    def test_invalid_new_image_changes_nothing(self) -> None:
        setup = _Setup(size=(800, 800))
        event = setup.repo.add(location="Salão")

        with pytest.raises(EventImageInvalidError):
            setup.service.update_event(
                event.id, EventPatchDTO(location="Templo"), _poster(), uuid4()
            )
        assert setup.repo.records[event.id] == event
        assert setup.storage.deleted == []

    def test_failed_row_write_keeps_the_old_file(self) -> None:
        setup = _Setup()
        event = setup.repo.add()
        setup.repo.fail_next_write = True

        with pytest.raises(RuntimeError):
            setup.service.update_event(event.id, EventPatchDTO(), _poster(), uuid4())
        assert setup.storage.files == {}
        assert event.image_path not in setup.storage.deleted

    def test_date_rule_is_checked_on_the_resulting_event(self) -> None:
        setup = _Setup()
        event = setup.repo.add(start_date=date(2026, 11, 10))

        with pytest.raises(EventDatesInvalidError):
            setup.service.update_event(
                event.id, EventPatchDTO(end_date=date(2026, 11, 8)), None, uuid4()
            )

    def test_clearing_end_date_makes_a_one_day_event(self) -> None:
        setup = _Setup()
        event = setup.repo.add(end_date=date(2026, 11, 16))

        updated = setup.service.update_event(event.id, EventPatchDTO(end_date=None), None, uuid4())

        assert updated.end_date is None

    def test_missing_event_is_not_found(self) -> None:
        with pytest.raises(EventNotFoundError):
            _Setup().service.update_event(99, EventPatchDTO(title="X"), None, uuid4())

    @pytest.mark.parametrize("with_image", [False, True])
    def test_records_the_editor(self, with_image: bool) -> None:
        setup = _Setup()
        event = setup.repo.add()
        editor = uuid4()
        image = _poster() if with_image else None

        updated = setup.service.update_event(event.id, EventPatchDTO(), image, editor)

        assert updated.updated_by is not None and updated.updated_by.id == editor


class TestDelete:
    def test_removes_row_and_file(self) -> None:
        setup = _Setup()
        event = setup.repo.add()

        setup.service.delete_event(event.id)

        assert event.id not in setup.repo.records
        assert setup.storage.deleted == [event.image_path]

    def test_missing_event_is_not_found(self) -> None:
        with pytest.raises(EventNotFoundError):
            _Setup().service.delete_event(99)
