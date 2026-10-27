"""``POST /api/photos/`` with a video, with real files in a temporary MEDIA_ROOT, and videos read
back by members (specs/023-gallery-videos US1, US2; contracts/video-upload-api.md)."""

from pathlib import Path

import pytest
from rest_framework.response import Response
from rest_framework.test import APIClient

from conftest import make_member_client
from features.gallery.models.gallery import Album, Photo
from features.gallery.tests.integration.helpers import (
    decoded_size,
    gallery_manager,
    image_file,
    text_file,
    video_file,
)
from features.gallery.tests.support import stored_name

PHOTOS_URL = "/api/photos/"
UPLOAD_ID = "video-3f2a9c1e-7b4d"


def _upload(client: APIClient, album_id: int, **changes: object) -> Response:
    body: dict[str, object] = {
        "album_id": album_id,
        "video": video_file(),
        "poster": image_file("poster.jpg", size=(1920, 1080)),
        "duration_ms": "45000",
        "client_upload_id": UPLOAD_ID,
    }
    body.update(changes)
    response: Response = client.post(
        PHOTOS_URL, {key: value for key, value in body.items() if value is not None}, "multipart"
    )
    return response


def _stored_files(media_root: Path) -> set[Path]:
    return {path for path in media_root.rglob("*") if path.is_file()}


@pytest.mark.django_db
@pytest.mark.usefixtures("media_root")
class TestAcceptedVideo:
    def test_mp4_is_stored_as_sent_with_a_poster_thumbnail(self, media_root: Path) -> None:
        album = Album.objects.create(name="Retiro 2026")
        sent = video_file().getvalue()

        response = _upload(gallery_manager(), album.pk, date_taken="2026-03-14")

        assert response.status_code == 201
        item = response.data["accepted"][0]
        assert (item["media_type"], item["duration_ms"], item["file_size"]) == (
            "video",
            45000,
            len(sent),
        )
        assert (item["name"], item["date_taken"]) == ("VID_0042.mp4", "2026-03-14")
        assert item["image_url"].endswith(".mp4")
        row = Photo.objects.get(pk=item["id"])
        assert (media_root / stored_name(row.image)).read_bytes() == sent
        assert decoded_size((media_root / stored_name(row.thumbnail)).read_bytes()) == (1000, 563)

    def test_mov_is_stored_with_its_extension(self) -> None:
        album = Album.objects.create(name="Retiro 2026")

        response = _upload(gallery_manager(), album.pk, video=video_file("IMG.MOV", b"qt  "))

        assert response.data["accepted"][0]["image_url"].endswith(".mov")

    def test_the_poster_becomes_the_first_cover(self) -> None:
        album = Album.objects.create(name="Retiro 2026")

        _upload(gallery_manager(), album.pk)

        album.refresh_from_db()
        assert stored_name(album.cover_image).startswith(f"gallery/covers/{album.pk}/")

    def test_a_retry_is_201_with_the_same_video(self, media_root: Path) -> None:
        client = gallery_manager()
        album = Album.objects.create(name="Retiro 2026")
        first = _upload(client, album.pk)
        files_after_first = _stored_files(media_root)

        second = _upload(client, album.pk)

        assert second.status_code == 201
        assert second.data["accepted"][0]["id"] == first.data["accepted"][0]["id"]
        assert _stored_files(media_root) == files_after_first

    def test_a_retry_of_a_trashed_video_is_409(self) -> None:
        client = gallery_manager()
        album = Album.objects.create(name="Retiro 2026")
        video_id = _upload(client, album.pk).data["accepted"][0]["id"]
        client.delete(f"/api/photos/{video_id}/")

        response = _upload(client, album.pk)

        assert response.status_code == 409
        assert response.data["client_upload_id"] == UPLOAD_ID


@pytest.mark.django_db
@pytest.mark.usefixtures("media_root")
class TestRefusedVideo:
    def test_mkv_is_400_with_the_reason_and_stores_nothing(self, media_root: Path) -> None:
        album = Album.objects.create(name="Retiro 2026")
        mkv = text_file("clip.mkv")

        response = _upload(gallery_manager(), album.pk, video=mkv)

        assert response.status_code == 400
        assert response.data["detail"] == "O vídeo não foi aceito."
        assert response.data["rejected"] == [
            {"filename": "clip.mkv", "reason": "Formato de vídeo não suportado. Use MP4 ou MOV."}
        ]
        assert _stored_files(media_root) == set()
        assert not Photo.objects.exists()

    def test_an_invalid_poster_is_400(self) -> None:
        album = Album.objects.create(name="Retiro 2026")

        response = _upload(gallery_manager(), album.pk, poster=text_file("poster.jpg"))

        assert response.status_code == 400
        assert response.data["rejected"][0]["reason"].startswith("Imagem de capa: ")

    @pytest.mark.parametrize(
        "changes",
        [
            {"poster": None},
            {"duration_ms": None},
            {"duration_ms": "0"},
            {"duration_ms": "45.5"},
            {"duration_ms": ["45000", "46000"]},
            {"client_upload_id": None},
            {"client_upload_id": " padded"},
            {"date_taken": "14/03/2026"},
            {"video": [video_file("a.mp4"), video_file("b.mp4")]},
            {"image": image_file()},
        ],
        ids=[
            "no-poster",
            "no-duration",
            "zero-duration",
            "fractional-duration",
            "duration-twice",
            "no-upload-id",
            "padded-upload-id",
            "bad-date",
            "two-videos",
            "image-and-video",
        ],
    )
    def test_a_malformed_request_is_400_and_stores_nothing(
        self, media_root: Path, changes: dict[str, object]
    ) -> None:
        album = Album.objects.create(name="Retiro 2026")

        response = _upload(gallery_manager(), album.pk, **changes)

        assert response.status_code == 400
        assert response.data["error_code"] == "VALIDATION_ERROR"
        assert _stored_files(media_root) == set()

    def test_an_empty_date_is_null(self) -> None:
        album = Album.objects.create(name="Retiro 2026")

        response = _upload(gallery_manager(), album.pk, date_taken="")

        assert response.data["accepted"][0]["date_taken"] is None

    def test_unknown_album_is_404(self) -> None:
        assert _upload(gallery_manager(), 999).status_code == 404

    def test_a_member_without_gallery_scope_is_403(self) -> None:
        album = Album.objects.create(name="Retiro 2026")
        client, _ = make_member_client()

        assert _upload(client, album.pk).status_code == 403


@pytest.mark.django_db
@pytest.mark.usefixtures("media_root")
class TestMembersReadVideos:
    def test_lists_and_feed_carry_photos_and_videos_alike(self) -> None:
        manager = gallery_manager()
        album = Album.objects.create(name="Retiro 2026")
        manager.post(PHOTOS_URL, {"album_id": album.pk, "image": image_file()}, "multipart")
        _upload(manager, album.pk)
        member, _ = make_member_client()

        listed = member.get(f"/api/albums/{album.pk}/photos/").data
        fed = member.get("/api/gallery/changes/").data["photos"]

        for items in (listed, fed):
            kinds = sorted((item["media_type"], item["duration_ms"]) for item in items)
            assert kinds == [("photo", None), ("video", 45000)]
            assert all(item["file_size"] > 0 for item in items)

    def test_the_video_file_is_served_as_video(self, settings: object) -> None:
        album = Album.objects.create(name="Retiro 2026")
        item = _upload(gallery_manager(), album.pk).data["accepted"][0]
        member, _ = make_member_client()
        setattr(settings, "DEBUG", False)

        response = member.get(item["image_url"])

        assert response.status_code == 200
        assert response["Content-Type"] == "video/mp4"
        assert response["X-Accel-Redirect"].endswith(".mp4")
        assert response["Cache-Control"] == "private, no-cache"

    def test_patch_cannot_change_the_media_fields(self) -> None:
        manager = gallery_manager()
        album = Album.objects.create(name="Retiro 2026")
        video_id = _upload(manager, album.pk).data["accepted"][0]["id"]

        response = manager.patch(f"/api/photos/{video_id}/", {"media_type": "photo"}, format="json")

        assert response.status_code == 400
        assert Photo.objects.get(pk=video_id).media_type == "video"
