"""Uploads with a client upload id: a retry of a photo already stored returns it and stores
nothing, a trashed original is refused, and a lost race leaves nothing behind
(specs/016-photo-upload-idempotency US1, US2, US5). Named fakes; ``django_db`` only because the
service opens transactions."""

import io
import logging
from uuid import uuid4

import pytest
from PIL import Image

from core.domain.exceptions import (
    ClientUploadNeedsOneFileError,
    InvalidClientUploadIdError,
    NoPhotoAcceptedError,
    UploadedPhotoTrashedError,
)
from features.gallery.dtos.gallery_dtos import ClientUploadMatch, NewPhoto
from features.gallery.services.album_cover_service import AlbumCoverService
from features.gallery.services.cover_change_tracker import CoverChangeTracker
from features.gallery.services.gallery_service import GalleryService
from features.gallery.tests.fakes import (
    FakeAlbumRepository,
    FakeGalleryFileStorage,
    FakeGalleryRepository,
    FakeImageProcessor,
)

UPLOAD_ID = "3f2a9c1e-7b4d-4e8a-9f10-2c6b5d7e8a90"
UPLOADER = uuid4()


def _image(name: str = "IMG_0042.jpg") -> io.BytesIO:
    buffer = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buffer, format="JPEG")
    buffer.seek(0)
    buffer.name = name
    setattr(buffer, "size", buffer.getbuffer().nbytes)
    return buffer


def _not_an_image() -> io.BytesIO:
    buffer = io.BytesIO(b"not-an-image")
    buffer.name = "bad.jpg"
    setattr(buffer, "size", 12)
    return buffer


class UploadSetup:
    def __init__(self) -> None:
        self.albums = FakeAlbumRepository()
        self.photos = FakeGalleryRepository(self.albums)
        self.storage = FakeGalleryFileStorage()
        self.images = FakeImageProcessor()
        covers = AlbumCoverService(
            self.albums, self.storage, self.images, CoverChangeTracker(self.albums)
        )
        self.service = GalleryService(self.photos, self.albums, self.storage, self.images, covers)
        self.album_id = self.albums.add("Retiro 2026")

    def upload(self, album_id: int | None = None, file: io.BytesIO | None = None) -> int:
        """Upload one file with ``UPLOAD_ID``; the id of the photo in the answer."""
        result = self.service.upload_photos(
            album_id or self.album_id, [file or _image()], UPLOADER, UPLOAD_ID
        )
        assert result.rejected == []
        return result.accepted[0].id

    def trash(self, photo_id: int) -> None:
        self.photos.trashed[photo_id] = self.photos.photos.pop(photo_id)

    def purge(self, photo_id: int) -> None:
        self.photos.trashed.pop(photo_id)


def _competitor(album_id: int) -> NewPhoto:
    return NewPhoto(
        album_id=album_id,
        image_name=f"gallery/{album_id}/winner.jpg",
        thumbnail_name=f"gallery/thumbs/{album_id}/winner.jpg",
        name="winner.jpg",
        date_taken=None,
        uploader_id=None,
        client_upload_id=UPLOAD_ID,
    )


@pytest.mark.django_db
class TestFirstUpload:
    def test_stores_the_id_and_answers_like_an_upload_without_one(self) -> None:
        setup = UploadSetup()

        photo_id = setup.upload()

        assert setup.photos.upload_ids == {UPLOAD_ID: photo_id}
        assert setup.photos.created[0].client_upload_id == UPLOAD_ID
        assert setup.photos.photos[photo_id].name == "IMG_0042.jpg"
        assert len(setup.storage.files) == 3  # original, thumbnail, automatic cover

    def test_a_rejected_file_stores_no_id(self) -> None:
        setup = UploadSetup()

        with pytest.raises(NoPhotoAcceptedError):
            setup.upload(file=_not_an_image())

        assert setup.photos.upload_ids == {}

    def test_malformed_id_is_refused_before_the_lookup(self) -> None:
        setup = UploadSetup()

        with pytest.raises(InvalidClientUploadIdError):
            setup.service.upload_photos(setup.album_id, [_image()], UPLOADER, "a b")

        assert setup.photos.upload_lookups == []

    def test_two_files_are_refused_before_the_lookup(self) -> None:
        setup = UploadSetup()

        with pytest.raises(ClientUploadNeedsOneFileError):
            setup.service.upload_photos(setup.album_id, [_image(), _image()], UPLOADER, UPLOAD_ID)

        assert setup.photos.upload_lookups == [] and setup.storage.files == {}


@pytest.mark.django_db
class TestRetryOfALivePhoto:
    def test_returns_the_same_photo_and_stores_nothing(self) -> None:
        setup = UploadSetup()
        photo_id = setup.upload()
        files_before = dict(setup.storage.files)
        derivatives_before = len(setup.images.bounded_calls) + len(setup.images.square_calls)

        assert setup.upload() == photo_id

        assert list(setup.photos.photos) == [photo_id]
        assert setup.storage.files == files_before
        after = len(setup.images.bounded_calls) + len(setup.images.square_calls)
        assert after == derivatives_before

    def test_the_file_of_a_retry_is_never_examined(self) -> None:
        setup = UploadSetup()
        photo_id = setup.upload()

        assert setup.upload(file=_not_an_image()) == photo_id

    def test_returns_the_photo_in_its_current_album(self) -> None:
        setup = UploadSetup()
        photo_id = setup.upload()
        other = setup.albums.add("Culto")
        setup.photos.move_photo(photo_id, other)

        result = setup.service.upload_photos(setup.album_id, [_image()], UPLOADER, UPLOAD_ID)

        assert (result.accepted[0].id, result.accepted[0].album_id) == (photo_id, other)

    def test_an_unknown_album_is_not_looked_up(self) -> None:
        setup = UploadSetup()
        photo_id = setup.upload()

        assert setup.upload(album_id=999) == photo_id

    def test_returns_the_current_resource(self) -> None:
        setup = UploadSetup()
        photo_id = setup.upload()
        setup.photos.update_photo(photo_id, {"description": "Culto de Páscoa"})

        result = setup.service.upload_photos(setup.album_id, [_image()], UPLOADER, UPLOAD_ID)

        assert result.accepted[0].description == "Culto de Páscoa"


@pytest.mark.django_db
class TestRetryAfterDelete:
    def test_trashed_original_is_refused_and_stays_in_the_trash(self) -> None:
        setup = UploadSetup()
        photo_id = setup.upload()
        setup.trash(photo_id)

        with pytest.raises(UploadedPhotoTrashedError):
            setup.upload()

        assert setup.photos.photos == {} and list(setup.photos.trashed) == [photo_id]

    def test_restored_original_is_returned_again(self) -> None:
        setup = UploadSetup()
        photo_id = setup.upload()
        setup.trash(photo_id)
        setup.photos.photos[photo_id] = setup.photos.trashed.pop(photo_id)

        assert setup.upload() == photo_id

    def test_purged_original_frees_the_id(self) -> None:
        setup = UploadSetup()
        first = setup.upload()
        setup.trash(first)
        setup.purge(first)

        second = setup.upload()

        assert second != first and setup.photos.upload_ids[UPLOAD_ID] == second


@pytest.mark.django_db
class TestLostRace:
    def test_answers_with_the_winner_and_removes_its_own_files(self) -> None:
        setup = UploadSetup()
        setup.photos.competing_upload = _competitor(setup.album_id)

        photo_id = setup.upload()

        assert setup.photos.photos[photo_id].name == "winner.jpg"
        assert list(setup.photos.photos) == [photo_id]
        assert setup.storage.files == {}  # the loser's original and thumbnail were deleted
        assert setup.albums.records[setup.album_id].cover_name == ""

    def test_winner_trashed_meanwhile_is_refused(self) -> None:
        setup = UploadSetup()
        setup.photos.competing_upload = _competitor(setup.album_id)
        original_match = setup.photos.find_client_upload

        def trash_then_find(client_upload_id: str) -> ClientUploadMatch | None:
            if setup.photos.photos:
                setup.trash(next(iter(setup.photos.photos)))
            return original_match(client_upload_id)

        setup.photos.find_client_upload = trash_then_find  # type: ignore[method-assign]

        with pytest.raises(UploadedPhotoTrashedError):
            setup.upload()


@pytest.mark.django_db
class TestLogs:
    def _events(self, caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
        return [r for r in caplog.records if r.getMessage().startswith("gallery_upload_")]

    def test_retry_logs_one_deduplicated_line_with_ids(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        setup = UploadSetup()
        photo_id = setup.upload()
        caplog.set_level(logging.INFO, logger="features.gallery")

        setup.upload()

        [record] = self._events(caplog)
        assert record.getMessage() == "gallery_upload_deduplicated"
        assert (getattr(record, "photo_id"), getattr(record, "actor_id")) == (
            photo_id,
            str(UPLOADER),
        )
        assert "IMG_0042" not in str(record.__dict__)

    def test_lost_race_logs_the_same_line(self, caplog: pytest.LogCaptureFixture) -> None:
        setup = UploadSetup()
        setup.photos.competing_upload = _competitor(setup.album_id)
        caplog.set_level(logging.INFO, logger="features.gallery")

        setup.upload()

        assert [r.getMessage() for r in self._events(caplog)] == ["gallery_upload_deduplicated"]

    def test_trashed_original_logs_its_own_line(self, caplog: pytest.LogCaptureFixture) -> None:
        setup = UploadSetup()
        photo_id = setup.upload()
        setup.trash(photo_id)
        caplog.set_level(logging.INFO, logger="features.gallery")

        with pytest.raises(UploadedPhotoTrashedError):
            setup.upload()

        [record] = self._events(caplog)
        assert record.getMessage() == "gallery_upload_original_trashed"
        assert getattr(record, "photo_id") == photo_id

    def test_first_upload_logs_neither(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO, logger="features.gallery")

        UploadSetup().upload()

        assert self._events(caplog) == []
