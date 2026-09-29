"""GalleryChangeFeedService with named fakes and a fake clock (specs/014-gallery-trash-sync)."""

from datetime import timedelta
from uuid import uuid4

import pytest

from features.gallery.domain.feed_cursor import decode_cursor, encode_cursor
from features.gallery.services.album_service import AlbumService
from features.gallery.services.cover_change_tracker import CoverChangeTracker
from features.gallery.services.gallery_change_feed_service import GalleryChangeFeedService
from features.gallery.services.gallery_trash_service import GalleryTrashService
from features.gallery.tests.fakes import (
    FakeAlbumRepository,
    FakeGalleryFileStorage,
    FakeGalleryRepository,
)
from features.gallery.tests.trash_fakes import FakeDeletionMarkRepository, FakeTrashRepository


class Setup:
    def __init__(self) -> None:
        self.albums = FakeAlbumRepository()
        self.clock = self.albums.clock
        self.photos = FakeGalleryRepository(self.albums)
        self.marks = FakeDeletionMarkRepository(self.clock)
        storage = FakeGalleryFileStorage()
        tracker = CoverChangeTracker(self.albums)
        album_service = AlbumService(self.albums, storage, tracker)
        self.feed = GalleryChangeFeedService(
            album_service, self.albums, self.photos, self.marks, self.clock
        )
        self.trash = GalleryTrashService(
            self.albums,
            self.photos,
            FakeTrashRepository(self.albums, self.photos),
            self.marks,
            tracker,
            album_service,
            storage,
        )
        self.album = self.albums.add("A")
        self.photo = self.photos.add(self.album)

    def cursor_after(self, delta: timedelta) -> str:
        """A cursor issued ``delta`` after the setup rows were written, so they fall outside
        its overlap; later writes are what the next delta must return."""
        self.clock.advance(delta)
        return self.feed.changes(None).cursor


@pytest.mark.django_db
class TestFullSync:
    def test_everything_without_a_cursor(self) -> None:
        setup = Setup()

        feed = setup.feed.changes(None)

        assert [a.id for a in feed.albums] == [setup.album]
        assert [p.id for p in feed.photos] == [setup.photo]
        assert (feed.deleted_album_ids, feed.deleted_photo_ids) == ([], [])
        assert not feed.full_sync_required
        assert decode_cursor(feed.cursor) == setup.clock.now()


@pytest.mark.django_db
class TestDelta:
    def test_only_what_changed_after_the_overlap(self) -> None:
        setup = Setup()
        cursor = setup.cursor_after(timedelta(minutes=10))
        new_album = setup.albums.add("B")

        feed = setup.feed.changes(cursor)

        assert [a.id for a in feed.albums] == [new_album]
        assert feed.photos == []

    def test_a_change_just_inside_the_overlap_comes_again(self) -> None:
        setup = Setup()
        setup.clock.advance(timedelta(minutes=10))
        setup.photos.update_photo(setup.photo, {"name": "late.jpg"})
        setup.clock.advance(timedelta(seconds=60))

        feed = setup.feed.changes(encode_cursor(setup.clock.now()))

        assert [p.id for p in feed.photos] == [setup.photo]

    def test_a_change_before_the_overlap_is_not_returned(self) -> None:
        setup = Setup()
        setup.clock.advance(timedelta(seconds=91))

        feed = setup.feed.changes(encode_cursor(setup.clock.now()))

        assert (feed.albums, feed.photos) == ([], [])

    def test_deleted_ids_include_cascaded_photos(self) -> None:
        setup = Setup()
        child = setup.albums.add("B", parent_id=setup.album)
        child_photo = setup.photos.add(child)
        cursor = setup.cursor_after(timedelta(minutes=10))

        setup.trash.delete_album(setup.album, uuid4())
        feed = setup.feed.changes(cursor)

        assert feed.deleted_album_ids == [setup.album, child]
        assert feed.deleted_photo_ids == sorted([setup.photo, child_photo])
        assert (feed.albums, feed.photos) == ([], [])

    def test_restored_item_is_changed_not_deleted(self) -> None:
        setup = Setup()
        setup.trash.delete_photo(setup.photo, uuid4())
        cursor = setup.cursor_after(timedelta(minutes=10))

        setup.trash.restore_photo(setup.photo)
        feed = setup.feed.changes(cursor)

        assert [p.id for p in feed.photos] == [setup.photo]
        assert feed.deleted_photo_ids == []


@pytest.mark.django_db
class TestFullSyncRequired:
    @pytest.mark.parametrize("raw", ["garbage", "", "v2.AAZck90e4AA"])
    def test_unreadable_cursor(self, raw: str) -> None:
        feed = Setup().feed.changes(raw)

        assert feed.full_sync_required
        assert (feed.albums, feed.photos, feed.deleted_photo_ids) == ([], [], [])

    def test_cursor_older_than_the_marks(self) -> None:
        setup = Setup()
        cursor = setup.feed.changes(None).cursor
        setup.clock.advance(timedelta(days=90))

        assert setup.feed.changes(cursor).full_sync_required

    def test_cursor_from_the_future(self) -> None:
        setup = Setup()
        future = encode_cursor(setup.clock.now() + timedelta(minutes=5))

        assert setup.feed.changes(future).full_sync_required
