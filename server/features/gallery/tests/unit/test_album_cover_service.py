"""AlbumCoverService with named fakes. ``django_db`` because the service opens transactions and
registers on-commit deletes; every row lives in the fakes."""

import io

import pytest
from PIL import Image

from core.domain.exceptions import AlbumNotFoundError, ImageTooLargeError, ValidationError
from features.gallery.services.album_cover_service import AlbumCoverService
from features.gallery.tests.support import CaptureOnCommit
from features.gallery.tests.fakes import (
    FakeAlbumRepository,
    FakeGalleryFileStorage,
    FakeImageProcessor,
)


def _image(name: str = "capa.png") -> io.BytesIO:
    buffer = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buffer, format="PNG")
    buffer.seek(0)
    buffer.name = name
    return buffer


class Setup:
    def __init__(self, processor: FakeImageProcessor | None = None) -> None:
        self.albums = FakeAlbumRepository()
        self.storage = FakeGalleryFileStorage()
        self.images = processor or FakeImageProcessor()
        self.service = AlbumCoverService(self.albums, self.storage, self.images)
        self.album_id = self.albums.add("Retiros")

    @property
    def cover(self) -> str:
        return self.albums.records[self.album_id].cover_name


@pytest.mark.django_db
class TestReplaceCover:
    def test_stores_the_square_and_deletes_the_old_after_commit(
        self, django_capture_on_commit_callbacks: CaptureOnCommit
    ) -> None:
        setup = Setup()
        setup.albums.set_cover_name(setup.album_id, "gallery/covers/1/old.jpg")

        with django_capture_on_commit_callbacks(execute=True):
            setup.service.replace_cover(setup.album_id, _image())

        assert setup.cover.startswith("gallery/covers/1/")
        assert setup.storage.files[setup.cover] == FakeImageProcessor.COVER
        assert setup.images.square_calls == [("capa.png", 1000, 85)]
        assert setup.storage.deleted == ["gallery/covers/1/old.jpg"]

    def test_invalid_image_keeps_the_previous_cover(self) -> None:
        setup = Setup()
        setup.albums.set_cover_name(setup.album_id, "gallery/covers/1/old.jpg")
        not_an_image = io.BytesIO(b"text")
        not_an_image.name = "x.jpg"

        with pytest.raises(ValidationError):
            setup.service.replace_cover(setup.album_id, not_an_image)

        assert setup.cover == "gallery/covers/1/old.jpg"
        assert setup.storage.files == {}

    def test_over_the_pixel_limit(self) -> None:
        setup = Setup(FakeImageProcessor(size=(10000, 6000)))

        with pytest.raises(ImageTooLargeError):
            setup.service.replace_cover(setup.album_id, _image())

    def test_unknown_album(self) -> None:
        with pytest.raises(AlbumNotFoundError):
            Setup().service.replace_cover(99, _image())


@pytest.mark.django_db
class TestRemoveCover:
    def test_removes_and_deletes_the_file_after_commit(
        self, django_capture_on_commit_callbacks: CaptureOnCommit
    ) -> None:
        setup = Setup()
        setup.albums.set_cover_name(setup.album_id, "gallery/covers/1/old.jpg")

        with django_capture_on_commit_callbacks(execute=True):
            setup.service.remove_cover(setup.album_id)

        assert setup.cover == ""
        assert setup.storage.deleted == ["gallery/covers/1/old.jpg"]

    def test_without_a_cover_is_a_no_op(self) -> None:
        setup = Setup()

        setup.service.remove_cover(setup.album_id)
        setup.service.remove_cover(setup.album_id)

        assert setup.storage.deleted == []

    def test_unknown_album(self) -> None:
        with pytest.raises(AlbumNotFoundError):
            Setup().service.remove_cover(99)


class TestFirstCover:
    def test_needed_only_without_photos_and_cover(self) -> None:
        setup = Setup()
        assert setup.service.needs_first_cover(setup.album_id)

        setup.albums.albums_with_photos.add(setup.album_id)
        assert not setup.service.needs_first_cover(setup.album_id)

    def test_not_needed_with_an_own_cover(self) -> None:
        setup = Setup()
        setup.albums.set_cover_name(setup.album_id, "gallery/covers/1/own.jpg")

        assert not setup.service.needs_first_cover(setup.album_id)

    def test_cover_from_photo_sets_the_cover(self) -> None:
        setup = Setup()

        setup.service.cover_from_photo(setup.album_id, _image("IMG.jpg"))

        assert setup.cover.startswith("gallery/covers/1/")

    def test_a_concurrent_cover_wins_and_the_new_file_is_deleted(self) -> None:
        setup = Setup()
        setup.albums.set_cover_name(setup.album_id, "gallery/covers/1/other.jpg")

        setup.service.cover_from_photo(setup.album_id, _image("IMG.jpg"))

        assert setup.cover == "gallery/covers/1/other.jpg"
        assert setup.storage.files == {}

    def test_failure_is_swallowed(self) -> None:
        setup = Setup(FakeImageProcessor(failing_names=frozenset({"IMG.jpg"})))

        setup.service.cover_from_photo(setup.album_id, _image("IMG.jpg"))

        assert setup.cover == ""
