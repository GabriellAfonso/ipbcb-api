"""GalleryTrashService with named fakes. ``django_db`` only because the service opens
transactions; every row lives in the fakes (specs/014-gallery-trash-sync)."""

import logging
from datetime import date, timedelta
from uuid import uuid4

import pytest

from core.domain.exceptions import (
    AlbumNotFoundError,
    AlbumRestoreNameConflictError,
    PhotoNotFoundError,
    TrashedParentError,
    TrashEntryNotFoundError,
)
from features.gallery.domain.trash_rules import TrashedItemKind
from features.gallery.services.album_service import AlbumService
from features.gallery.services.cover_change_tracker import CoverChangeTracker
from features.gallery.services.gallery_trash_service import GalleryTrashService
from features.gallery.tests.fakes import (
    FakeAlbumRepository,
    FakeGalleryFileStorage,
    FakeGalleryRepository,
)
from features.gallery.tests.trash_fakes import FakeDeletionMarkRepository, FakeTrashRepository

ALBUM, PHOTO = TrashedItemKind.ALBUM, TrashedItemKind.PHOTO
ACTOR = uuid4()


class Setup:
    """A → B → C, one photo in each, plus P1 directly in A."""

    def __init__(self) -> None:
        self.albums = FakeAlbumRepository()
        self.photos = FakeGalleryRepository(self.albums)
        self.trash = FakeTrashRepository(self.albums, self.photos)
        self.marks = FakeDeletionMarkRepository(self.albums.clock)
        storage = FakeGalleryFileStorage()
        tracker = CoverChangeTracker(self.albums)
        self.service = GalleryTrashService(
            self.albums,
            self.photos,
            self.trash,
            self.marks,
            tracker,
            AlbumService(self.albums, storage, tracker),
            storage,
        )
        self.a = self.albums.add("A")
        self.b = self.albums.add("B", parent_id=self.a)
        self.c = self.albums.add("C", parent_id=self.b)
        self.pa, self.pb, self.pc = (self.photos.add(i) for i in (self.a, self.b, self.c))
        self.p1 = self.photos.add(self.a, "p1.jpg")


@pytest.mark.django_db
class TestDeletePhoto:
    def test_trashes_in_a_batch_of_one_with_a_mark(self) -> None:
        setup = Setup()

        outcome = setup.service.delete_photo(setup.p1, ACTOR)

        assert outcome.photo_ids == [setup.p1] and outcome.album_ids == []
        assert setup.p1 in setup.photos.trashed and setup.p1 not in setup.photos.photos
        assert (PHOTO, setup.p1) in setup.marks.marks
        assert setup.trash.batches[outcome.batch_id][:3] == (PHOTO, setup.p1, ACTOR)

    def test_second_delete_is_not_found_and_makes_no_batch(self) -> None:
        setup = Setup()
        setup.service.delete_photo(setup.p1, ACTOR)

        with pytest.raises(PhotoNotFoundError):
            setup.service.delete_photo(setup.p1, ACTOR)
        assert len(setup.trash.batches) == 1

    def test_unknown_photo_is_not_found(self) -> None:
        with pytest.raises(PhotoNotFoundError):
            Setup().service.delete_photo(999, ACTOR)

    def test_logs_ids_and_counts_only(self, caplog: pytest.LogCaptureFixture) -> None:
        setup = Setup()
        with caplog.at_level(logging.INFO, logger="features.gallery"):
            setup.service.delete_photo(setup.p1, ACTOR)

        record = next(r for r in caplog.records if r.getMessage() == "gallery_trashed")
        assert (record.__dict__["kind"], record.__dict__["id"]) == ("photo", setup.p1)
        assert record.__dict__["actor_id"] == str(ACTOR)
        assert (record.__dict__["album_count"], record.__dict__["photo_count"]) == (0, 1)
        assert "p1.jpg" not in str(record.__dict__)


@pytest.mark.django_db
class TestDeleteAlbum:
    def test_cascades_the_subtree_in_one_batch(self) -> None:
        setup = Setup()

        outcome = setup.service.delete_album(setup.a, ACTOR)

        assert outcome.album_ids == [setup.a, setup.b, setup.c]
        assert outcome.photo_ids == sorted([setup.pa, setup.pb, setup.pc, setup.p1])
        assert setup.albums.records == {} and setup.photos.photos == {}
        assert set(setup.trash.album_batch.values()) == {outcome.batch_id}
        assert {k for k, _ in setup.marks.marks} == {ALBUM, PHOTO}
        assert len(setup.marks.marks) == 7
        assert setup.albums.locked_parent_map

    def test_photo_trashed_earlier_keeps_its_batch(self) -> None:
        setup = Setup()
        first = setup.service.delete_photo(setup.p1, ACTOR)
        setup.albums.clock.advance(timedelta(hours=1))

        outcome = setup.service.delete_album(setup.a, ACTOR)

        assert setup.p1 not in outcome.photo_ids
        assert setup.trash.photo_batch[setup.p1] == first.batch_id
        assert setup.marks.marks[(PHOTO, setup.p1)] == setup.albums.clock.START

    def test_second_delete_is_not_found(self) -> None:
        setup = Setup()
        setup.service.delete_album(setup.a, ACTOR)

        with pytest.raises(AlbumNotFoundError):
            setup.service.delete_album(setup.b, ACTOR)

    def test_parent_inheriting_the_cover_is_touched(self) -> None:
        setup = Setup()
        root = setup.albums.add("Root")
        child = setup.albums.add("Child", parent_id=root, cover_name="c.jpg")

        setup.service.delete_album(child, ACTOR)

        assert root in setup.albums.touched


@pytest.mark.django_db
class TestRestore:
    def test_album_restore_brings_back_exactly_its_batch(self) -> None:
        setup = Setup()
        setup.service.delete_photo(setup.p1, ACTOR)
        setup.service.delete_album(setup.a, ACTOR)

        view = setup.service.restore_album(setup.a)

        assert view.id == setup.a
        assert set(setup.albums.records) == {setup.a, setup.b, setup.c}
        assert set(setup.photos.photos) == {setup.pa, setup.pb, setup.pc}
        assert setup.p1 in setup.photos.trashed
        assert (PHOTO, setup.p1) in setup.marks.marks
        assert (ALBUM, setup.a) not in setup.marks.marks

    def test_positions_are_kept(self) -> None:
        setup = Setup()
        position = setup.albums.records[setup.b].position
        setup.service.delete_album(setup.b, ACTOR)

        setup.service.restore_album(setup.b)

        assert setup.albums.records[setup.b].position == position

    def test_member_of_another_batch_cannot_be_restored_alone(self) -> None:
        setup = Setup()
        setup.service.delete_album(setup.a, ACTOR)

        with pytest.raises(TrashEntryNotFoundError):
            setup.service.restore_album(setup.b)
        with pytest.raises(TrashEntryNotFoundError):
            setup.service.restore_photo(setup.pa)

    def test_live_or_unknown_is_not_found(self) -> None:
        setup = Setup()
        with pytest.raises(TrashEntryNotFoundError):
            setup.service.restore_album(setup.a)
        with pytest.raises(TrashEntryNotFoundError):
            setup.service.restore_photo(999)

    def test_photo_under_a_trashed_album_is_refused_until_the_album_is_back(self) -> None:
        setup = Setup()
        setup.service.delete_photo(setup.p1, ACTOR)
        setup.service.delete_album(setup.a, ACTOR)

        with pytest.raises(TrashedParentError) as refused:
            setup.service.restore_photo(setup.p1)
        assert refused.value.extra_context() == {
            "kind": "photo",
            "id": setup.p1,
            "trashed_parent_id": setup.a,
        }
        assert setup.p1 in setup.photos.trashed

        setup.service.restore_album(setup.a)
        assert setup.service.restore_photo(setup.p1).id == setup.p1

    def test_album_under_a_trashed_parent_is_refused(self) -> None:
        setup = Setup()
        setup.service.delete_album(setup.c, ACTOR)
        setup.service.delete_album(setup.a, ACTOR)

        with pytest.raises(TrashedParentError):
            setup.service.restore_album(setup.c)

    def test_name_conflict_is_refused_until_the_sibling_is_renamed(self) -> None:
        setup = Setup()
        setup.service.delete_album(setup.b, ACTOR)
        rival = setup.albums.add("B", parent_id=setup.a)

        with pytest.raises(AlbumRestoreNameConflictError) as refused:
            setup.service.restore_album(setup.b)
        assert refused.value.extra_context()["conflicting_album_id"] == rival
        assert setup.b in setup.albums.trashed

        setup.albums.update(rival, {"name": "B (novo)"})
        assert setup.service.restore_album(setup.b).name == "B"

    def test_restored_rows_are_touched(self) -> None:
        setup = Setup()
        setup.service.delete_album(setup.b, ACTOR)
        setup.albums.clock.advance(timedelta(hours=2))

        setup.service.restore_album(setup.b)

        now = setup.albums.clock.now()
        assert setup.albums.records[setup.b].updated_at == now
        assert setup.photos.photos[setup.pb].updated_at == now


@pytest.mark.django_db
class TestListTrash:
    def test_one_entry_per_batch_with_counts_and_purge_date(self) -> None:
        setup = Setup()
        setup.service.delete_photo(setup.p1, ACTOR)
        setup.albums.clock.advance(timedelta(minutes=5))
        setup.service.delete_album(setup.a, ACTOR)

        entries = setup.service.list_trash()

        assert [(e.kind, e.id) for e in entries] == [(ALBUM, setup.a), (PHOTO, setup.p1)]
        album_entry = entries[0]
        assert (album_entry.sub_album_count, album_entry.photo_count) == (2, 3)
        assert album_entry.purge_on == date(2026, 10, 29)
        assert (entries[1].sub_album_count, entries[1].photo_count) == (0, 0)
