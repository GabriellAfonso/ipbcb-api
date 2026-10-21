from datetime import date, time
from pathlib import Path

import pytest
from django.db import IntegrityError, transaction
from pytest_django import DjangoAssertNumQueries

from conftest import make_user
from core.domain.exceptions import EventNotFoundError
from features.events.domain.event_enums import EventStatusFilter, EventVisibility
from features.events.dtos import EventCreateDTO
from features.events.models.event import Event
from features.events.repositories.event_image_lookup import EventImageLookupImpl
from features.events.repositories.event_image_storage import DefaultStorageEventImageStorage
from features.events.repositories.event_repository import EventRepositoryImpl
from features.events.tests.integration.conftest import TODAY, MakeEvent

REPOSITORY = EventRepositoryImpl()


@pytest.mark.django_db
class TestReads:
    def test_list_active_orders_all_day_first_and_filters_members(
        self, make_event: MakeEvent
    ) -> None:
        timed = make_event(start_time=time(8, 0))
        all_day = make_event()
        members = make_event(visibility=EventVisibility.MEMBERS)
        make_event(start_date=date(2026, 11, 13))

        public_ids = [r.id for r in REPOSITORY.list_active(TODAY, include_members=False)]
        all_ids = [r.id for r in REPOSITORY.list_active(TODAY, include_members=True)]

        assert public_ids == [all_day.pk, timed.pk]
        assert all_ids == [all_day.pk, members.pk, timed.pk]

    def test_multi_day_event_is_active_until_its_end_date(self, make_event: MakeEvent) -> None:
        event = make_event(start_date=date(2026, 11, 10), end_date=TODAY)

        assert REPOSITORY.get_active(event.pk, TODAY, include_members=False) is not None

    @pytest.mark.parametrize(
        ("status", "expected"), [("active", ["now"]), ("past", ["old"]), ("all", ["now", "old"])]
    )
    def test_list_all_by_status(
        self, make_event: MakeEvent, status: str, expected: list[str]
    ) -> None:
        events = {"now": make_event(), "old": make_event(start_date=date(2026, 1, 1))}

        listed = REPOSITORY.list_all(EventStatusFilter(status), TODAY)

        assert [r.id for r in listed] == [events[name].pk for name in expected]

    def test_list_is_one_query(
        self, make_event: MakeEvent, django_assert_num_queries: DjangoAssertNumQueries
    ) -> None:
        user = make_user(username="ana")
        for _ in range(3):
            Event.objects.filter(pk=make_event().pk).update(created_by=user)

        with django_assert_num_queries(1):
            REPOSITORY.list_all(EventStatusFilter.ALL, TODAY)


@pytest.mark.django_db
class TestWrites:
    def test_create_records_the_creator_with_profile_name(self) -> None:
        user = make_user(username="ana")
        user.profile.name = "Ana Paula"
        user.profile.save()
        dto = EventCreateDTO(title="Retiro", start_date=TODAY)

        record = REPOSITORY.create(dto, "events/x.jpg", user.pk)

        assert record.created_by is not None
        assert (record.created_by.id, record.created_by.name) == (user.pk, "Ana Paula")

    def test_deleted_creator_leaves_the_event(self, make_event: MakeEvent) -> None:
        user = make_user(username="ana")
        record = REPOSITORY.create(
            EventCreateDTO(title="R", start_date=TODAY), "events/y.jpg", user.pk
        )
        user.delete()

        reloaded = REPOSITORY.get(record.id)

        assert reloaded is not None and reloaded.created_by is None

    def test_update_applies_changes_and_image(self, make_event: MakeEvent) -> None:
        event = make_event()

        record = REPOSITORY.update(
            event.pk, {"location": "Templo"}, "events/new.jpg", make_user(username="bia").pk
        )

        assert (record.location, record.image_path) == ("Templo", "events/new.jpg")

    def test_update_missing_raises(self) -> None:
        with pytest.raises(EventNotFoundError):
            REPOSITORY.update(999, {}, None, make_user(username="bia").pk)

    def test_delete_removes_the_row(self, make_event: MakeEvent) -> None:
        event = make_event()

        REPOSITORY.delete(event.pk)

        assert REPOSITORY.get(event.pk) is None

    def test_database_refuses_end_before_start(self, make_event: MakeEvent) -> None:
        event = make_event()

        with pytest.raises(IntegrityError), transaction.atomic():
            Event.objects.filter(pk=event.pk).update(end_date=date(2026, 11, 1))


@pytest.mark.django_db
class TestImageLookup:
    def test_answers_by_visibility_or_none(self, make_event: MakeEvent) -> None:
        public = make_event()
        members = make_event(visibility=EventVisibility.MEMBERS)
        lookup = EventImageLookupImpl()

        assert lookup.is_public_event_image(public.image_path) is True
        assert lookup.is_public_event_image(members.image_path) is False
        assert lookup.is_public_event_image("events/none.jpg") is None


class TestImageStorage:
    def test_save_url_delete(self, media_root: Path) -> None:
        storage = DefaultStorageEventImageStorage()

        name = storage.save(b"\xff\xd8jpeg")

        assert name.startswith("events/") and name.endswith(".jpg")
        assert (media_root / name).read_bytes() == b"\xff\xd8jpeg"
        assert storage.url(name) == f"/ipbcb/media/{name}"
        storage.delete(name)
        storage.delete(name)  # already gone: not an error
        assert not (media_root / name).exists()
