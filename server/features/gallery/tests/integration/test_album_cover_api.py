"""Automatic and manual album covers (specs/013-gallery-write-api US4)."""

from pathlib import Path

import pytest

from core.domain.access import Role
from features.gallery.models.gallery import Album, Photo
from features.gallery.tests.support import CaptureOnCommit, stored_name
from features.gallery.tests.integration.helpers import (
    decoded_size,
    gallery_manager,
    image_file,
    text_file,
)


def _cover_url(album: Album) -> str:
    return f"/api/albums/{album.pk}/cover/"


def _upload(album: Album, *names: str) -> None:
    files = [image_file(name) for name in names]
    response = gallery_manager(username="uploader").post(
        "/api/photos/", {"album_id": album.pk, "image": files}, format="multipart"
    )
    assert response.status_code == 201


@pytest.mark.django_db
@pytest.mark.usefixtures("media_root")
class TestAutomaticCover:
    def test_first_upload_into_an_empty_album(self, media_root: Path) -> None:
        album = Album.objects.create(name="Retiros")

        _upload(album, "first.jpg", "second.jpg")

        album.refresh_from_db()
        assert stored_name(album.cover_image).startswith(f"gallery/covers/{album.pk}/")
        assert decoded_size((media_root / stored_name(album.cover_image)).read_bytes()) == (
            1000,
            1000,
        )

    def test_moving_the_source_photo_keeps_the_cover(self) -> None:
        album = Album.objects.create(name="Retiros")
        other = Album.objects.create(name="Cultos")
        _upload(album, "first.jpg")
        album.refresh_from_db()
        cover = stored_name(album.cover_image)

        photo = Photo.objects.get(album=album)
        gallery_manager().patch(f"/api/photos/{photo.pk}/", {"album_id": other.pk}, format="json")

        album.refresh_from_db()
        assert stored_name(album.cover_image) == cover

    def test_album_with_photos_keeps_no_cover(self) -> None:
        album = Album.objects.create(name="Retiros")
        Photo.objects.create(album=album, name="old.jpg", image="gallery/old.jpg")

        _upload(album, "new.jpg")

        album.refresh_from_db()
        assert stored_name(album.cover_image) == ""


@pytest.mark.django_db
@pytest.mark.usefixtures("media_root")
class TestManualCover:
    def test_put_replaces_and_deletes_the_old_file(
        self, media_root: Path, django_capture_on_commit_callbacks: CaptureOnCommit
    ) -> None:
        album = Album.objects.create(name="Retiros")
        _upload(album, "first.jpg")
        album.refresh_from_db()
        old = media_root / stored_name(album.cover_image)

        with django_capture_on_commit_callbacks(execute=True):
            response = gallery_manager().put(
                _cover_url(album),
                {"image": image_file("capa.png", (500, 300), "PNG")},
                format="multipart",
            )

        album.refresh_from_db()
        assert response.status_code == 200
        assert response.data["cover_source_album_id"] == album.pk
        assert decoded_size((media_root / stored_name(album.cover_image)).read_bytes()) == (
            1000,
            1000,
        )
        assert not old.exists()

    def test_invalid_image_is_400_and_keeps_the_cover(self) -> None:
        album = Album.objects.create(name="Retiros", cover_image="gallery/covers/1/c.jpg")

        response = gallery_manager().put(
            _cover_url(album), {"image": text_file()}, format="multipart"
        )

        assert response.status_code == 400
        album.refresh_from_db()
        assert stored_name(album.cover_image) == "gallery/covers/1/c.jpg"

    def test_missing_file_is_400(self) -> None:
        album = Album.objects.create(name="Retiros")

        assert gallery_manager().put(_cover_url(album), {}, format="multipart").status_code == 400

    @pytest.mark.parametrize("role", [Role.LEADER, Role.MEDIA])
    def test_delete_by_leader_or_media_falls_back_to_sub_albums(
        self, role: Role, django_capture_on_commit_callbacks: CaptureOnCommit
    ) -> None:
        album = Album.objects.create(name="Retiros", cover_image="gallery/covers/1/own.jpg")
        child = Album.objects.create(
            name="2026", parent=album, cover_image="gallery/covers/2/c.jpg"
        )
        client = gallery_manager(role, f"{role.value}_deleter")

        with django_capture_on_commit_callbacks(execute=True):
            response = client.delete(_cover_url(album))

        assert response.status_code == 204
        listed = {a["id"]: a for a in client.get("/api/albums/").data}
        assert listed[album.pk]["cover_source_album_id"] == child.pk

    def test_delete_without_a_cover_is_204_and_regenerates_nothing(self) -> None:
        album = Album.objects.create(name="Retiros")
        Photo.objects.create(album=album, name="a.jpg", image="gallery/a.jpg")

        assert gallery_manager().delete(_cover_url(album)).status_code == 204
        _upload(album, "later.jpg")

        album.refresh_from_db()
        assert stored_name(album.cover_image) == ""

    @pytest.mark.parametrize("method", ["put", "delete"])
    def test_unknown_album_is_404(self, method: str) -> None:
        body = {"image": image_file()} if method == "put" else None
        response = getattr(gallery_manager(), method)(
            "/api/albums/9999/cover/", body, format="multipart"
        )

        assert response.status_code == 404
