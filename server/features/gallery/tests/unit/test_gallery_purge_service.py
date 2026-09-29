"""GalleryPurgeService with named fakes. ``django_db`` because each batch runs in a transaction
and its file deletes wait for the commit (specs/014-gallery-trash-sync FR-031–FR-033)."""

from datetime import timedelta
from uuid import UUID, uuid4

import pytest

from features.gallery.domain.trash_rules import TrashedItemKind
from features.gallery.dtos.trash_dtos import PurgeReport
from features.gallery.management.commands.purge_gallery_trash import summary_line
from features.gallery.services.gallery_purge_service import GalleryPurgeService
from features.gallery.tests.fakes import (
    FakeAlbumRepository,
    FakeGalleryFileStorage,
    FakeGalleryRepository,
)
from features.gallery.tests.trash_fakes import FakeDeletionMarkRepository, FakeTrashRepository
from features.gallery.tests.support import CaptureOnCommit


class Setup:
    def __init__(self) -> None:
        self.albums = FakeAlbumRepository()
        self.clock = self.albums.clock
        self.photos = FakeGalleryRepository(self.albums)
        self.trash = FakeTrashRepository(self.albums, self.photos)
        self.marks = FakeDeletionMarkRepository(self.clock)
        self.storage = FakeGalleryFileStorage()
        self.service = GalleryPurgeService(self.trash, self.marks, self.storage, self.clock)

    def trashed_photo(self, name: str = "a.jpg") -> tuple[int, UUID]:
        album = self.albums.add(f"album-{name}")
        photo = self.photos.add(album, name, thumbnail=f"gallery/thumbs/{album}/{name}")
        batch = self.trash.create_batch(TrashedItemKind.PHOTO, photo, None)
        self.trash.trash_photo(photo, batch)
        self.marks.upsert(TrashedItemKind.PHOTO, [photo])
        return photo, batch


@pytest.mark.django_db
class TestPurgeExpired:
    def test_only_batches_older_than_thirty_days(
        self, django_capture_on_commit_callbacks: CaptureOnCommit
    ) -> None:
        setup = Setup()
        old_photo, old_batch = setup.trashed_photo("old.jpg")
        setup.clock.advance(timedelta(days=25))
        _, recent_batch = setup.trashed_photo("recent.jpg")
        setup.clock.advance(timedelta(days=6))

        with django_capture_on_commit_callbacks(execute=True):
            report = setup.service.purge_expired()

        assert (report.batches, report.photos) == (1, 1)
        assert setup.trash.purged == [old_batch]
        assert recent_batch in setup.trash.batches
        assert len(setup.storage.deleted) == 2  # original and thumbnail
        assert all(name.endswith("old.jpg") for name in setup.storage.deleted)
        assert old_photo not in setup.photos.trashed

    def test_a_failing_batch_is_skipped_and_the_next_still_purged(
        self, django_capture_on_commit_callbacks: CaptureOnCommit
    ) -> None:
        setup = Setup()
        _, failing = setup.trashed_photo("bad.jpg")
        _, fine = setup.trashed_photo("good.jpg")
        setup.trash.failing_batches.add(failing)
        setup.clock.advance(timedelta(days=31))

        with django_capture_on_commit_callbacks(execute=True):
            report = setup.service.purge_expired()

        assert report.skipped_batch_ids == [failing]
        assert setup.trash.purged == [fine]
        assert all("bad.jpg" not in name for name in setup.storage.deleted)

    def test_marks_survive_the_purge_and_expire_after_ninety_days(self) -> None:
        setup = Setup()
        photo, _ = setup.trashed_photo()
        setup.clock.advance(timedelta(days=31))

        setup.service.purge_expired()
        assert (TrashedItemKind.PHOTO, photo) in setup.marks.marks

        setup.clock.advance(timedelta(days=60))
        report = setup.service.purge_expired()
        assert report.marks_expired == 1
        assert setup.marks.marks == {}

    def test_second_run_purges_nothing(self) -> None:
        setup = Setup()
        setup.trashed_photo()
        setup.clock.advance(timedelta(days=31))
        setup.service.purge_expired()

        assert setup.service.purge_expired().batches == 0


def test_summary_line() -> None:
    batch = uuid4()
    report = PurgeReport(
        batches=3, albums=2, photos=45, skipped_batch_ids=[batch], marks_expired=12
    )

    assert summary_line(report) == (
        f"purged 3 batches (2 albums, 45 photos); skipped 1: ['{batch}']; expired 12 marks"
    )
