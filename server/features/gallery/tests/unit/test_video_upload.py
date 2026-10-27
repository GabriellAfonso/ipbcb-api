"""Video uploads through ``GalleryService.upload_video``: the video stored as sent, the poster as
thumbnail and first cover, retries answered from the stored item, nothing left behind on a
refusal (specs/023-gallery-videos US1). Named fakes; ``django_db`` only because the service opens
transactions."""

import io
from datetime import date
from uuid import uuid4

import pytest
from PIL import Image

from core.domain.exceptions import (
    AlbumNotFoundError,
    InvalidClientUploadIdError,
    NoVideoAcceptedError,
    UploadedPhotoTrashedError,
)
from core.files.video_validation import MAX_VIDEO_BYTES
from features.gallery.dtos.gallery_dtos import NewPhoto, VideoUploadMeta
from features.gallery.services.album_cover_service import AlbumCoverService
from features.gallery.services.cover_change_tracker import CoverChangeTracker
from features.gallery.services.gallery_service import GalleryService
from features.gallery.tests.fakes import (
    FakeAlbumRepository,
    FakeGalleryFileStorage,
    FakeGalleryRepository,
    FakeImageProcessor,
)

UPLOAD_ID = "9c1e3f2a-7b4d-4e8a-9f10-2c6b5d7e8a90"
UPLOADER = uuid4()


def _video(name: str = "VID_0042.mp4", brand: bytes = b"isom") -> io.BytesIO:
    buffer = io.BytesIO(b"\x00\x00\x00\x18ftyp" + brand + b"\x00" * 100)
    buffer.name = name
    setattr(buffer, "size", buffer.getbuffer().nbytes)
    return buffer


def _mkv() -> io.BytesIO:
    buffer = io.BytesIO(b"\x1a\x45\xdf\xa3" + b"\x00" * 100)
    buffer.name = "clip.mkv"
    return buffer


def _poster(name: str = "poster.jpg") -> io.BytesIO:
    buffer = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buffer, format="JPEG")
    buffer.seek(0)
    buffer.name = name
    setattr(buffer, "size", buffer.getbuffer().nbytes)
    return buffer


def _meta(**changes: object) -> VideoUploadMeta:
    return VideoUploadMeta(duration_ms=45000, client_upload_id=UPLOAD_ID).model_copy(update=changes)


class VideoUploadSetup:
    def __init__(self, album_cover: str = "") -> None:
        self.albums = FakeAlbumRepository()
        self.photos = FakeGalleryRepository(self.albums)
        self.storage = FakeGalleryFileStorage()
        self.images = FakeImageProcessor()
        covers = AlbumCoverService(
            self.albums, self.storage, self.images, CoverChangeTracker(self.albums)
        )
        self.service = GalleryService(self.photos, self.albums, self.storage, self.images, covers)
        self.album_id = self.albums.add("Retiro 2026", cover_name=album_cover)

    def upload(
        self, video: io.BytesIO | None = None, poster: io.BytesIO | None = None, **meta: object
    ) -> list[int]:
        result = self.service.upload_video(
            self.album_id, video or _video(), poster or _poster(), _meta(**meta), UPLOADER
        )
        return [item.id for item in result.accepted]


@pytest.mark.django_db
class TestAcceptedVideo:
    def test_stores_the_video_as_sent_with_its_poster_as_thumbnail(self) -> None:
        setup = VideoUploadSetup()
        video = _video()

        result = setup.service.upload_video(setup.album_id, video, _poster(), _meta(), UPLOADER)

        item = result.accepted[0]
        assert (item.media_type, item.duration_ms, item.file_size) == ("video", 45000, 112)
        assert item.image_path == "/ipbcb/media/gallery/1/1.mp4"
        assert setup.storage.files["gallery/1/1.mp4"] == video.getvalue()
        assert setup.storage.files["gallery/thumbs/1/2.jpg"] == FakeImageProcessor.THUMBNAIL
        assert setup.images.bounded_calls == [("poster.jpg", 1000, 85)]

    def test_records_name_date_uploader_and_upload_id(self) -> None:
        setup = VideoUploadSetup()

        setup.upload(date_taken=date(2026, 3, 14))

        created: NewPhoto = setup.photos.created[0]
        assert created.name == "VID_0042.mp4"
        assert created.date_taken == date(2026, 3, 14)
        assert (created.uploader_id, created.client_upload_id) == (UPLOADER, UPLOAD_ID)

    def test_a_quicktime_video_is_stored_as_mov(self) -> None:
        setup = VideoUploadSetup()

        setup.upload(video=_video("IMG_0042.MOV", b"qt  "))

        assert setup.photos.created[0].image_name == "gallery/1/1.mov"

    def test_the_poster_gives_an_empty_album_its_first_cover(self) -> None:
        setup = VideoUploadSetup()

        setup.upload()

        assert setup.images.square_calls == [("poster.jpg", 1000, 85)]
        assert setup.albums.records[setup.album_id].cover_name.startswith("gallery/covers/")

    def test_an_album_with_its_own_cover_keeps_it(self) -> None:
        setup = VideoUploadSetup(album_cover="gallery/covers/1/own.jpg")

        setup.upload()

        assert setup.albums.records[setup.album_id].cover_name == "gallery/covers/1/own.jpg"


@pytest.mark.django_db
class TestRefusedVideo:
    @pytest.mark.parametrize(
        "video",
        [_mkv(), _video("clip.3gp", b"3gp5")],
        ids=["mkv", "3gpp"],
    )
    def test_a_wrong_format_stores_nothing(self, video: io.BytesIO) -> None:
        setup = VideoUploadSetup()

        with pytest.raises(NoVideoAcceptedError) as caught:
            setup.upload(video=video)

        assert caught.value.rejected == [
            {"filename": video.name, "reason": "Formato de vídeo não suportado. Use MP4 ou MOV."}
        ]
        assert (setup.storage.files, setup.photos.photos) == ({}, {})

    def test_an_oversized_video_is_refused(self) -> None:
        setup = VideoUploadSetup()
        video = _video()
        setattr(video, "size", MAX_VIDEO_BYTES + 1)

        with pytest.raises(NoVideoAcceptedError) as caught:
            setup.upload(video=video)

        assert "Vídeo muito grande: 104857601 bytes" in caught.value.rejected[0]["reason"]
        assert str(caught.value) == "O vídeo não foi aceito."

    def test_an_invalid_poster_refuses_the_video(self) -> None:
        setup = VideoUploadSetup()
        poster = io.BytesIO(b"not-an-image")
        poster.name = "poster.jpg"

        with pytest.raises(NoVideoAcceptedError) as caught:
            setup.upload(poster=poster)

        rejected = caught.value.rejected[0]
        assert rejected["filename"] == "VID_0042.mp4"
        assert rejected["reason"].startswith("Imagem de capa: Formato inválido")
        assert setup.storage.files == {}

    def test_a_poster_above_the_pixel_limit_refuses_the_video(self) -> None:
        setup = VideoUploadSetup()
        setup.images.size = (9000, 8000)

        with pytest.raises(NoVideoAcceptedError, match="vídeo"):
            setup.upload()

    def test_files_are_removed_when_the_row_fails(self) -> None:
        setup = VideoUploadSetup()
        setup.photos.fail_on_create = True

        with pytest.raises(RuntimeError):
            setup.upload()

        assert setup.storage.files == {}
        assert sorted(setup.storage.deleted) == ["gallery/1/1.mp4", "gallery/thumbs/1/2.jpg"]

    def test_unknown_album_is_not_found(self) -> None:
        setup = VideoUploadSetup()

        with pytest.raises(AlbumNotFoundError):
            setup.service.upload_video(99, _video(), _poster(), _meta(), UPLOADER)

    def test_a_malformed_upload_id_is_refused_before_any_lookup(self) -> None:
        setup = VideoUploadSetup()

        with pytest.raises(InvalidClientUploadIdError):
            setup.upload(client_upload_id="has space")

        assert setup.photos.upload_lookups == []


@pytest.mark.django_db
class TestRetriedVideo:
    def test_a_retry_returns_the_stored_video_and_stores_nothing(self) -> None:
        setup = VideoUploadSetup()
        first = setup.upload()
        files_after_first = dict(setup.storage.files)

        # Not even examined: a retry never reads the files it carries (spec 016).
        second = setup.upload(video=_mkv())

        assert second == first
        assert setup.storage.files == files_after_first

    def test_a_retry_of_a_trashed_video_is_refused(self) -> None:
        setup = VideoUploadSetup()
        [video_id] = setup.upload()
        setup.photos.trashed[video_id] = setup.photos.photos.pop(video_id)

        with pytest.raises(UploadedPhotoTrashedError):
            setup.upload()

    def test_a_lost_race_answers_with_the_winner(self) -> None:
        setup = VideoUploadSetup()
        setup.photos.competing_upload = NewPhoto(
            album_id=setup.album_id,
            image_name="gallery/1/winner.mp4",
            thumbnail_name="gallery/thumbs/1/winner.jpg",
            name="VID_0042.mp4",
            date_taken=None,
            uploader_id=UPLOADER,
            client_upload_id=UPLOAD_ID,
            media_type="video",
            duration_ms=45000,
        )

        [video_id] = setup.upload()

        assert setup.photos.images[video_id] == "gallery/1/winner.mp4"
        assert setup.storage.files == {}
