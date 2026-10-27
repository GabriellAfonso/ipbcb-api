"""A video behaves as a photo everywhere after upload: tags, trash, restore, purge, move, admin,
the database check, the backfill commands (specs/023-gallery-videos US3, US4)."""

from datetime import timedelta
from io import StringIO
from pathlib import Path

import pytest
from django.apps import apps
from django.core.management import call_command
from django.db import IntegrityError
from django.test import Client
from django.utils import timezone
from rest_framework.test import APIClient

from conftest import make_member_client
from features.accounts.models.user import User
from features.gallery.models.gallery import Album, Photo
from features.gallery.models.trash import GalleryDeletionBatch
from features.gallery.tests.integration.helpers import gallery_manager, image_file, video_file
from features.gallery.tests.support import CaptureOnCommit, stored_name


def _upload_video(album: Album, manager: APIClient) -> Photo:
    response = manager.post(
        "/api/photos/",
        {
            "album_id": album.pk,
            "video": video_file(),
            "poster": image_file("poster.jpg"),
            "duration_ms": "45000",
            "client_upload_id": f"video-{album.pk}",
        },
        "multipart",
    )
    return Photo.objects.get(pk=response.data["accepted"][0]["id"])


def _run(command: str) -> str:
    output = StringIO()
    call_command(command, stdout=output)
    return output.getvalue().strip()


@pytest.mark.django_db
@pytest.mark.usefixtures("media_root")
class TestVideoLikeAPhoto:
    def test_tags_and_the_member_filter_find_the_video(self) -> None:
        manager = gallery_manager()
        album = Album.objects.create(name="Retiro 2026")
        video = _upload_video(album, manager)
        ana = apps.get_model("members", "Member").objects.create(name="Ana")

        manager.put(f"/api/photos/{video.pk}/members/", {"member_ids": [ana.pk]}, format="json")

        member, _ = make_member_client()
        found = member.get(f"/api/photos/?member_id={ana.pk}").data
        assert [(item["id"], item["media_type"]) for item in found] == [(video.pk, "video")]

    def test_move_keeps_the_media_fields(self) -> None:
        manager = gallery_manager()
        album, other = Album.objects.create(name="A"), Album.objects.create(name="B")
        video = _upload_video(album, manager)

        response = manager.patch(f"/api/photos/{video.pk}/", {"album_id": other.pk}, format="json")

        assert (response.data["album_id"], response.data["media_type"]) == (other.pk, "video")
        assert response.data["duration_ms"] == 45000

    def test_trash_and_restore(self) -> None:
        manager = gallery_manager()
        album = Album.objects.create(name="Retiro 2026")
        video = _upload_video(album, manager)

        manager.delete(f"/api/photos/{video.pk}/")
        restored = manager.post(f"/api/gallery/trash/photos/{video.pk}/restore/")

        assert restored.status_code == 200
        assert Photo.objects.get(pk=video.pk).media_type == "video"

    def test_purge_removes_the_video_file_and_the_poster(
        self, media_root: Path, django_capture_on_commit_callbacks: CaptureOnCommit
    ) -> None:
        manager = gallery_manager()
        album = Album.objects.create(name="Retiro 2026", cover_image="gallery/covers/own.jpg")
        video = _upload_video(album, manager)
        files = [media_root / stored_name(video.image), media_root / stored_name(video.thumbnail)]
        manager.delete(f"/api/photos/{video.pk}/")
        GalleryDeletionBatch.objects.update(deleted_at=timezone.now() - timedelta(days=31))

        with django_capture_on_commit_callbacks(execute=True):
            _run("purge_gallery_trash")

        assert not Photo.all_objects.filter(pk=video.pk).exists()
        assert [path.exists() for path in files] == [False, False]


@pytest.mark.django_db
class TestStoredVideoRules:
    def test_a_video_without_duration_is_refused_by_the_database(self) -> None:
        album = Album.objects.create(name="Retiro 2026")

        with pytest.raises(IntegrityError):
            Photo.objects.create(
                album=album,
                name="v.mp4",
                image="gallery/1/v.mp4",
                thumbnail="t.jpg",
                media_type="video",
            )

    def test_a_video_without_poster_is_refused_by_the_database(self) -> None:
        album = Album.objects.create(name="Retiro 2026")

        with pytest.raises(IntegrityError):
            Photo.objects.create(
                album=album,
                name="v.mp4",
                image="gallery/1/v.mp4",
                media_type="video",
                duration_ms=1000,
            )

    def test_the_admin_shows_a_video_without_decoding_it(self) -> None:
        album = Album.objects.create(name="Retiro 2026")
        video = Photo.objects.create(
            album=album,
            name="v.mp4",
            image="gallery/1/v.mp4",
            thumbnail="gallery/thumbs/1/t.jpg",
            media_type="video",
            duration_ms=45000,
            file_size=10,
        )
        client = Client()
        client.force_login(User.objects.create_superuser(username="site_admin", password="x1"))

        response = client.get(f"/admin/gallery/photo/{video.pk}/change/")

        assert response.status_code == 200
        assert b"45000" in response.content


@pytest.mark.django_db
class TestBackfills:
    def test_file_sizes_are_filled_once_and_missing_files_listed(self, media_root: Path) -> None:
        album = Album.objects.create(name="Culto")
        original = media_root / "gallery" / "culto" / "IMG_0042.jpg"
        original.parent.mkdir(parents=True)
        original.write_bytes(b"12345")
        present = Photo.objects.create(
            album=album, name="a.jpg", image="gallery/culto/IMG_0042.jpg"
        )
        missing = Photo.objects.create(album=album, name="b.jpg", image="gallery/culto/gone.jpg")
        before = Photo.objects.get(pk=present.pk).updated_at

        first = _run("fill_gallery_file_sizes")

        present.refresh_from_db()
        assert first == f"filled 1, skipped 1: ids [{missing.pk}]"
        assert present.file_size == 5
        assert present.updated_at > before
        assert _run("fill_gallery_file_sizes") == f"filled 0, skipped 1: ids [{missing.pk}]"

    def test_upload_records_the_photo_size(self, media_root: Path) -> None:
        album = Album.objects.create(name="Culto")
        sent = image_file()

        response = gallery_manager().post(
            "/api/photos/", {"album_id": album.pk, "image": sent}, "multipart"
        )

        assert response.data["accepted"][0]["file_size"] == len(sent.getvalue())
