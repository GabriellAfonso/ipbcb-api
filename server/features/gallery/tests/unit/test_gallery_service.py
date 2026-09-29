"""GalleryService with named fakes: no files, no Pillow derivatives. Validation still runs the
real ``core.files.image_validation`` on tiny generated images. ``django_db`` only because the
service opens transactions; every row lives in the fakes."""

import io
from datetime import date
from uuid import uuid4

import pytest
from PIL import Image

from core.domain.exceptions import (
    AlbumNotFoundError,
    NoPhotoAcceptedError,
    OrderMismatchError,
    PhotoNotFoundError,
    ValidationError,
)
from core.files.image_validation import MAX_IMAGE_BYTES
from features.gallery.dtos.gallery_dtos import PhotoChanges
from features.gallery.services.album_cover_service import AlbumCoverService
from features.gallery.services.gallery_service import GalleryService
from features.gallery.tests.fakes import (
    FakeAlbumRepository,
    FakeGalleryFileStorage,
    FakeGalleryRepository,
    FakeImageProcessor,
)


def _image(name: str = "photo.jpg", fmt: str = "JPEG") -> io.BytesIO:
    buffer = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buffer, format=fmt)
    buffer.seek(0)
    buffer.name = name
    setattr(buffer, "size", buffer.getbuffer().nbytes)
    return buffer


def _not_an_image(name: str = "bad.jpg") -> io.BytesIO:
    buffer = io.BytesIO(b"not-an-image")
    buffer.name = name
    setattr(buffer, "size", 12)
    return buffer


class Setup:
    def __init__(self, processor: FakeImageProcessor | None = None) -> None:
        self.albums = FakeAlbumRepository()
        self.photos = FakeGalleryRepository(self.albums)
        self.storage = FakeGalleryFileStorage()
        self.images = processor or FakeImageProcessor()
        covers = AlbumCoverService(self.albums, self.storage, self.images)
        self.service = GalleryService(self.photos, self.albums, self.storage, self.images, covers)
        self.album_id = self.albums.add("Retiros")


class TestUploadPhotos:
    def test_accepts_a_valid_file_with_thumbnail_and_uploader(self) -> None:
        setup = Setup(FakeImageProcessor(taken_on=date(2026, 3, 14)))
        uploader = uuid4()

        result = setup.service.upload_photos(setup.album_id, [_image("IMG_0042.jpg")], uploader)

        assert [photo.name for photo in result.accepted] == ["IMG_0042.jpg"]
        assert result.rejected == []
        created = setup.photos.created[0]
        assert created.image_name.endswith(".jpg") and created.image_name.startswith("gallery/1/")
        assert created.thumbnail_name.startswith("gallery/thumbs/1/")
        assert (created.date_taken, created.uploader_id) == (date(2026, 3, 14), uploader)
        assert setup.images.bounded_calls == [("IMG_0042.jpg", 1000, 85)]

    def test_extension_comes_from_the_decoded_format(self) -> None:
        setup = Setup()

        setup.service.upload_photos(setup.album_id, [_image("fake.jpg", fmt="PNG")])

        assert setup.photos.created[0].image_name.endswith(".png")

    def test_partial_success_keeps_the_valid_file(self) -> None:
        setup = Setup()

        result = setup.service.upload_photos(setup.album_id, [_image("ok.jpg"), _not_an_image()])

        assert [photo.name for photo in result.accepted] == ["ok.jpg"]
        assert result.rejected[0].filename == "bad.jpg"
        assert "formato" in result.rejected[0].reason.lower()

    def test_every_file_rejected_raises_with_every_reason(self) -> None:
        setup = Setup()
        big = _image("big.jpg")
        setattr(big, "size", MAX_IMAGE_BYTES + 1)

        with pytest.raises(NoPhotoAcceptedError) as caught:
            setup.service.upload_photos(setup.album_id, [big, _not_an_image()])

        assert [item["filename"] for item in caught.value.rejected] == ["big.jpg", "bad.jpg"]
        assert "muito grande" in caught.value.rejected[0]["reason"]
        assert setup.storage.files == {}

    def test_over_the_pixel_limit_is_rejected_before_any_derivative(self) -> None:
        setup = Setup(FakeImageProcessor(size=(9000, 8000)))

        with pytest.raises(NoPhotoAcceptedError) as caught:
            setup.service.upload_photos(setup.album_id, [_image("huge.jpg")])

        assert "50 megapixels" in caught.value.rejected[0]["reason"]
        assert setup.images.bounded_calls == []

    def test_thumbnail_failure_rejects_and_keeps_nothing(self) -> None:
        setup = Setup(FakeImageProcessor(failing_names=frozenset({"broken.jpg"})))

        result = setup.service.upload_photos(
            setup.album_id, [_image("broken.jpg"), _image("ok.jpg")]
        )

        assert result.rejected[0].filename == "broken.jpg"
        assert [photo.name for photo in result.accepted] == ["ok.jpg"]
        assert len(setup.photos.created) == 1

    def test_long_filename_is_cut_keeping_the_extension(self) -> None:
        setup = Setup()

        result = setup.service.upload_photos(setup.album_id, [_image("a" * 150 + ".jpg")])

        assert len(result.accepted[0].name) == 100
        assert result.accepted[0].name.endswith(".jpg")

    def test_unknown_album_touches_nothing(self) -> None:
        setup = Setup()

        with pytest.raises(AlbumNotFoundError):
            setup.service.upload_photos(999, [_image()])

        assert setup.storage.files == {}

    def test_database_failure_deletes_both_stored_files(self) -> None:
        setup = Setup()
        setup.photos.fail_on_create = True

        with pytest.raises(RuntimeError):
            setup.service.upload_photos(setup.album_id, [_image()])

        assert setup.storage.files == {}
        assert len(setup.storage.deleted) == 2

    def test_photos_are_appended(self) -> None:
        setup = Setup()
        setup.photos.add(setup.album_id, "old.jpg")

        setup.service.upload_photos(setup.album_id, [_image("new.jpg")])

        names = [photo.name for photo in setup.service.list_photos_by_album(setup.album_id)]
        assert names == ["old.jpg", "new.jpg"]


class TestAutomaticCover:
    def test_first_accepted_photo_of_an_empty_album_becomes_its_cover(self) -> None:
        setup = Setup(FakeImageProcessor(failing_names=frozenset({"broken.jpg"})))

        setup.service.upload_photos(
            setup.album_id, [_image("broken.jpg"), _image("first.jpg"), _image("second.jpg")]
        )

        assert setup.images.square_calls == [("first.jpg", 1000, 85)]
        assert setup.albums.records[setup.album_id].cover_name.startswith("gallery/covers/1/")

    def test_album_with_photos_gets_no_automatic_cover(self) -> None:
        setup = Setup()
        setup.photos.add(setup.album_id)

        setup.service.upload_photos(setup.album_id, [_image()])

        assert setup.albums.records[setup.album_id].cover_name == ""

    def test_album_with_an_own_cover_keeps_it(self) -> None:
        setup = Setup()
        setup.albums.set_cover_name(setup.album_id, "gallery/covers/1/own.jpg")

        setup.service.upload_photos(setup.album_id, [_image()])

        assert setup.albums.records[setup.album_id].cover_name == "gallery/covers/1/own.jpg"

    def test_cover_failure_keeps_the_photo_accepted(self) -> None:
        processor = FakeImageProcessor()
        setup = Setup(processor)

        def fail(*args: object) -> bytes:
            raise ValidationError("cover failed")

        processor.square_jpeg = fail  # type: ignore[method-assign, assignment]

        result = setup.service.upload_photos(setup.album_id, [_image()])

        assert len(result.accepted) == 1
        assert setup.albums.records[setup.album_id].cover_name == ""


class TestReads:
    def test_photos_by_album_of_an_unknown_album_is_not_found(self) -> None:
        with pytest.raises(AlbumNotFoundError):
            Setup().service.list_photos_by_album(999)

    def test_all_photos_follow_the_album_tree_order(self) -> None:
        setup = Setup()
        child = setup.albums.add("2026", parent_id=setup.album_id)
        other_root = setup.albums.add("Cultos")
        setup.photos.add(other_root, "culto.jpg")
        setup.photos.add(child, "child.jpg")
        setup.photos.add(setup.album_id, "root.jpg")

        names = [photo.name for photo in setup.service.list_all_photos()]

        assert names == ["root.jpg", "child.jpg", "culto.jpg"]


@pytest.mark.django_db
class TestUpdatePhoto:
    def test_changes_only_the_sent_fields(self) -> None:
        setup = Setup()
        photo_id = setup.photos.add(setup.album_id, "a.jpg")

        photo = setup.service.update_photo(photo_id, PhotoChanges(description="Páscoa"))

        assert (photo.description, photo.name) == ("Páscoa", "a.jpg")

    def test_explicit_null_clears_the_date(self) -> None:
        setup = Setup()
        photo_id = setup.photos.add(setup.album_id)
        setup.photos.update_photo(photo_id, {"date_taken": date(2026, 1, 1)})

        photo = setup.service.update_photo(photo_id, PhotoChanges(date_taken=None))

        assert photo.date_taken is None

    def test_move_appends_to_the_target_album(self) -> None:
        setup = Setup()
        target = setup.albums.add("Cultos")
        setup.photos.add(target, "existing.jpg")
        photo_id = setup.photos.add(setup.album_id, "moved.jpg")

        setup.service.update_photo(photo_id, PhotoChanges(album_id=target))

        assert [p.name for p in setup.service.list_photos_by_album(target)] == [
            "existing.jpg",
            "moved.jpg",
        ]

    def test_unknown_photo(self) -> None:
        with pytest.raises(PhotoNotFoundError):
            Setup().service.update_photo(999, PhotoChanges(name="x.jpg"))

    def test_unknown_target_album(self) -> None:
        setup = Setup()
        photo_id = setup.photos.add(setup.album_id)

        with pytest.raises(AlbumNotFoundError):
            setup.service.update_photo(photo_id, PhotoChanges(album_id=999))


@pytest.mark.django_db
class TestReorderPhotos:
    def test_applies_the_exact_order(self) -> None:
        setup = Setup()
        first, second, third = (setup.photos.add(setup.album_id, f"{n}.jpg") for n in "abc")

        setup.service.reorder_photos(setup.album_id, [third, first, second])

        assert setup.photos.photo_ids(setup.album_id) == [third, first, second]

    def test_missing_id_changes_nothing(self) -> None:
        setup = Setup()
        first, second = (setup.photos.add(setup.album_id, f"{n}.jpg") for n in "ab")

        with pytest.raises(OrderMismatchError) as caught:
            setup.service.reorder_photos(setup.album_id, [second])

        assert caught.value.missing == [first]
        assert setup.photos.photo_ids(setup.album_id) == [first, second]

    def test_empty_album_accepts_an_empty_order(self) -> None:
        setup = Setup()

        setup.service.reorder_photos(setup.album_id, [])

    def test_unknown_album(self) -> None:
        with pytest.raises(AlbumNotFoundError):
            Setup().service.reorder_photos(999, [])


class TestFillMissingThumbnails:
    def test_fills_readable_and_skips_missing_originals(self) -> None:
        setup = Setup()
        readable = setup.photos.add(setup.album_id, "ok.jpg")
        setup.storage.files[setup.photos.images[readable]] = b"jpeg"
        missing = setup.photos.add(setup.album_id, "gone.jpg")

        report = setup.service.fill_missing_thumbnails()

        assert (report.filled, report.skipped_ids) == (1, [missing])
        assert setup.photos.thumbnails[readable].startswith("gallery/thumbs/1/")

    def test_second_run_changes_nothing(self) -> None:
        setup = Setup()
        photo_id = setup.photos.add(setup.album_id, "ok.jpg")
        setup.storage.files[setup.photos.images[photo_id]] = b"jpeg"
        setup.service.fill_missing_thumbnails()

        report = setup.service.fill_missing_thumbnails()

        assert (report.filled, report.skipped_ids) == (0, [])

    def test_undecodable_original_is_skipped(self) -> None:
        setup = Setup(FakeImageProcessor(failing_names=frozenset({"gallery/1/bad.jpg"})))
        photo_id = setup.photos.add(setup.album_id, "bad.jpg")
        setup.storage.files["gallery/1/bad.jpg"] = b"junk"

        assert setup.service.fill_missing_thumbnails().skipped_ids == [photo_id]
