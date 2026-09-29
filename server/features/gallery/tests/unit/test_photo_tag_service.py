"""PhotoTagService with named fakes (specs/015-gallery-member-tags). ``django_db`` only because
the service opens ``transaction.atomic()``; every row lives in the fakes."""

import logging
from datetime import timedelta
from uuid import uuid4

import pytest

from core.domain.exceptions import (
    PhotoNotFoundError,
    PhotoTagReferenceError,
    TagBulkLimitError,
    TagListOverlapError,
)
from features.gallery.dtos.tag_dtos import MemberRef, PhotoMembersReplace, PhotoTagsBulkChange
from features.gallery.services.photo_tag_service import PhotoTagService
from features.gallery.tests.fakes import FakeAlbumRepository, FakeGalleryRepository
from features.gallery.tests.tag_fakes import FakeMemberDirectory, FakePhotoTagRepository

ANA, BRUNO, CARLA = 12, 40, 7
ACTOR = uuid4()


class Setup:
    def __init__(self) -> None:
        self.albums = FakeAlbumRepository()
        self.photos = FakeGalleryRepository(self.albums)
        self.directory = FakeMemberDirectory({ANA: "Ana", BRUNO: "Bruno", CARLA: "Carla"})
        self.tags = FakePhotoTagRepository(self.photos, self.directory)
        self.service = PhotoTagService(self.tags, self.directory, self.photos)
        album = self.albums.add("A")
        self.p1 = self.photos.add(album, "1.jpg")
        self.p2 = self.photos.add(album, "2.jpg")

    def replace(self, photo_id: int, *member_ids: int) -> list[MemberRef]:
        change = PhotoMembersReplace(member_ids=list(member_ids))
        return self.service.replace_photo_members(photo_id, change, ACTOR).members

    def bulk(self, photos: list[int], add: list[int], remove: list[int]) -> list[int]:
        change = PhotoTagsBulkChange(photo_ids=photos, add_member_ids=add, remove_member_ids=remove)
        return [photo.id for photo in self.service.change_tags(change, ACTOR)]


@pytest.mark.django_db
class TestReplace:
    def test_adds_and_removes_to_match(self) -> None:
        setup = Setup()
        setup.tags.tag(setup.p1, ANA, BRUNO)

        members = setup.replace(setup.p1, BRUNO, CARLA)

        assert [m.id for m in members] == [BRUNO, CARLA]
        assert setup.tags.writes[0].added == {setup.p1: [CARLA]}
        assert setup.tags.writes[0].removed == {setup.p1: [ANA]}
        assert setup.tags.actors == [ACTOR]

    def test_empty_clears(self) -> None:
        setup = Setup()
        setup.tags.tag(setup.p1, ANA)

        assert setup.replace(setup.p1) == []

    def test_repeated_ids_count_once(self) -> None:
        setup = Setup()

        assert [m.id for m in setup.replace(setup.p1, ANA, ANA)] == [ANA]

    def test_same_set_writes_nothing_and_logs_nothing(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        setup = Setup()
        setup.tags.tag(setup.p1, ANA)
        before = setup.photos.get_photo(setup.p1)

        with caplog.at_level(logging.INFO, logger="features.gallery"):
            setup.replace(setup.p1, ANA)

        assert all(diff.is_empty for diff in setup.tags.writes)
        assert setup.photos.get_photo(setup.p1) == before
        assert "gallery_tags_changed" not in caplog.messages

    def test_unknown_or_trashed_photo_is_not_found(self) -> None:
        setup = Setup()

        with pytest.raises(PhotoNotFoundError):
            setup.replace(999, ANA)

    def test_unknown_members_are_all_listed_and_nothing_is_written(self) -> None:
        setup = Setup()

        with pytest.raises(PhotoTagReferenceError) as caught:
            setup.replace(setup.p1, ANA, 99, 98)

        assert caught.value.missing_member_ids == [98, 99]
        assert setup.tags.writes == []

    def test_member_deleted_during_the_write_is_reported_as_missing(self) -> None:
        setup = Setup()
        setup.tags.vanish_member_on_write = CARLA

        with pytest.raises(PhotoTagReferenceError) as caught:
            setup.replace(setup.p1, CARLA)

        assert caught.value.missing_member_ids == [CARLA]

    def test_logs_ids_only(self, caplog: pytest.LogCaptureFixture) -> None:
        setup = Setup()

        with caplog.at_level(logging.INFO, logger="features.gallery"):
            setup.replace(setup.p1, ANA)

        record = next(r for r in caplog.records if r.getMessage() == "gallery_tags_changed")
        assert record.photo_ids == [setup.p1]  # type: ignore[attr-defined]
        assert record.added == {str(setup.p1): [ANA]}  # type: ignore[attr-defined]
        assert record.removed == {}  # type: ignore[attr-defined]
        assert record.actor_id == str(ACTOR)  # type: ignore[attr-defined]
        assert "Ana" not in str(record.__dict__)


@pytest.mark.django_db
class TestBulk:
    def test_changes_only_the_listed_pairs(self) -> None:
        setup = Setup()
        setup.tags.tag(setup.p1, ANA, BRUNO)
        setup.tags.tag(setup.p2, BRUNO)

        setup.bulk([setup.p1, setup.p2], add=[CARLA], remove=[BRUNO])

        assert setup.tags.tags == {setup.p1: {ANA, CARLA}, setup.p2: {CARLA}}

    def test_answers_in_request_order(self) -> None:
        setup = Setup()

        assert setup.bulk([setup.p2, setup.p1, setup.p2], add=[ANA], remove=[]) == [
            setup.p2,
            setup.p1,
        ]

    def test_only_changed_photos_are_marked(self) -> None:
        setup = Setup()
        setup.tags.tag(setup.p1, ANA)
        setup.albums.clock.advance(timedelta(minutes=5))
        untouched = setup.photos.get_photo(setup.p1)

        setup.bulk([setup.p1, setup.p2], add=[ANA], remove=[])

        assert setup.photos.get_photo(setup.p1) == untouched
        assert setup.tags.writes[0].changed_photo_ids == [setup.p2]

    def test_missing_photos_and_members_in_one_error(self) -> None:
        setup = Setup()

        with pytest.raises(PhotoTagReferenceError) as caught:
            setup.bulk([setup.p1, 500, 501], add=[ANA, 99], remove=[])

        assert caught.value.missing_photo_ids == [500, 501]
        assert caught.value.missing_member_ids == [99]
        assert setup.tags.writes == []

    def test_overlap_and_limit_are_refused_before_any_read(self) -> None:
        setup = Setup()
        setup.photos.photos.clear()  # a read would now report every photo missing instead

        with pytest.raises(TagListOverlapError):
            setup.bulk([setup.p1], add=[ANA], remove=[ANA])
        with pytest.raises(TagBulkLimitError):
            setup.bulk(list(range(1, 202)), add=[ANA], remove=[])


@pytest.mark.django_db
class TestLists:
    def test_picker_is_every_member_by_name(self) -> None:
        setup = Setup()

        assert [m.name for m in setup.service.taggable_members()] == ["Ana", "Bruno", "Carla"]

    def test_tagged_members_counts_live_photos(self) -> None:
        setup = Setup()
        setup.tags.tag(setup.p1, ANA, BRUNO)
        setup.tags.tag(setup.p2, ANA)

        counts = {m.id: m.photo_count for m in setup.service.tagged_members()}

        assert counts == {ANA: 2, BRUNO: 1}
