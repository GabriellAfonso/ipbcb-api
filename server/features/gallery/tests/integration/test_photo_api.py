"""Photo upload, edit and move over the API, with real files in a temporary MEDIA_ROOT
(specs/013-gallery-write-api US1, US6; contracts/gallery-api.md)."""

import re
from pathlib import Path

import pytest

from features.gallery.models.gallery import Album, Photo
from features.gallery.tests.integration.helpers import (
    decoded_size,
    gallery_manager,
    image_file,
    text_file,
)

PHOTOS_URL = "/api/photos/"
_HEX = "[0-9a-f]{32}"


def _media_path(url: str, media_root: Path) -> Path:
    return media_root / url.split("/media/", 1)[1]


@pytest.mark.django_db
@pytest.mark.usefixtures("media_root")
class TestUpload:
    def test_single_photo_is_201_with_thumbnail(self, media_root: Path) -> None:
        album = Album.objects.create(name="Retiros")

        response = gallery_manager().post(
            PHOTOS_URL, {"album_id": album.pk, "image": image_file()}, format="multipart"
        )

        assert response.status_code == 201
        assert response.data["rejected"] == []
        photo = response.data["accepted"][0]
        assert (photo["name"], photo["description"], photo["album_id"]) == (
            "IMG_0042.jpg",
            "",
            album.pk,
        )
        assert re.search(rf"/ipbcb/media/gallery/{album.pk}/{_HEX}\.jpg$", photo["image_url"])
        assert re.search(rf"/media/gallery/thumbs/{album.pk}/{_HEX}\.jpg$", photo["thumbnail_url"])
        thumbnail = _media_path(photo["thumbnail_url"], media_root).read_bytes()
        assert decoded_size(thumbnail) == (1000, 750)
        assert "uploaded_by" not in photo

    def test_partial_upload_is_207(self) -> None:
        album = Album.objects.create(name="Retiros")
        files = [image_file("a.jpg"), image_file("b.png", fmt="PNG"), text_file("fake.jpg")]

        response = gallery_manager().post(
            PHOTOS_URL, {"album_id": album.pk, "image": files}, format="multipart"
        )

        assert response.status_code == 207
        assert [p["name"] for p in response.data["accepted"]] == ["a.jpg", "b.png"]
        assert response.data["rejected"][0]["filename"] == "fake.jpg"
        assert "Formato" in response.data["rejected"][0]["reason"]
        assert response.data["accepted"][1]["image_url"].endswith(".png")

    def test_nothing_accepted_is_the_canonical_400_with_rejected(self) -> None:
        album = Album.objects.create(name="Retiros")

        response = gallery_manager().post(
            PHOTOS_URL, {"album_id": album.pk, "image": [text_file("a.jpg")]}, format="multipart"
        )

        assert response.status_code == 400
        assert response.data["error_code"] == "VALIDATION_ERROR"
        assert response.data["detail"] == "Nenhuma imagem foi aceita."
        assert response.data["rejected"][0]["filename"] == "a.jpg"
        assert not Photo.objects.exists()

    def test_exif_date_becomes_date_taken(self) -> None:
        album = Album.objects.create(name="Retiros")
        upload = image_file(taken="2026:03:14 09:30:00")

        response = gallery_manager().post(
            PHOTOS_URL, {"album_id": album.pk, "image": upload}, format="multipart"
        )

        assert response.data["accepted"][0]["date_taken"] == "2026-03-14"

    def test_without_exif_date_taken_is_null(self) -> None:
        album = Album.objects.create(name="Retiros")

        response = gallery_manager().post(
            PHOTOS_URL, {"album_id": album.pk, "image": image_file()}, format="multipart"
        )

        assert response.data["accepted"][0]["date_taken"] is None

    def test_new_photo_goes_last(self) -> None:
        album = Album.objects.create(name="Retiros")
        Photo.objects.create(album=album, name="old.jpg", image="gallery/old.jpg", position=3)

        gallery_manager().post(
            PHOTOS_URL, {"album_id": album.pk, "image": image_file("new.jpg")}, format="multipart"
        )

        assert Photo.objects.get(name="new.jpg").position == 4

    def test_missing_album_id(self) -> None:
        response = gallery_manager().post(PHOTOS_URL, {"image": image_file()}, format="multipart")

        assert response.status_code == 400
        assert "album_id" in response.data["detail"]

    def test_missing_file(self) -> None:
        album = Album.objects.create(name="Retiros")

        response = gallery_manager().post(PHOTOS_URL, {"album_id": album.pk}, format="multipart")

        assert response.status_code == 400
        assert "image" in response.data["detail"]

    def test_unknown_album_is_404_and_stores_nothing(self, media_root: Path) -> None:
        response = gallery_manager().post(
            PHOTOS_URL, {"album_id": 9999, "image": image_file()}, format="multipart"
        )

        assert response.status_code == 404
        assert not any(media_root.rglob("*.jpg"))


@pytest.mark.django_db
@pytest.mark.usefixtures("media_root")
class TestPatch:
    def _photo(self, album: Album, name: str = "a.jpg", position: int = 0) -> Photo:
        return Photo.objects.create(
            album=album, name=name, image=f"gallery/x/{name}", position=position
        )

    def test_changes_only_the_sent_fields(self) -> None:
        photo = self._photo(Album.objects.create(name="Retiros"))

        response = gallery_manager().patch(
            f"{PHOTOS_URL}{photo.pk}/", {"description": "Culto de Páscoa"}, format="json"
        )

        assert response.status_code == 200
        assert (response.data["description"], response.data["name"]) == ("Culto de Páscoa", "a.jpg")

    def test_name_and_date(self) -> None:
        photo = self._photo(Album.objects.create(name="Retiros"))

        response = gallery_manager().patch(
            f"{PHOTOS_URL}{photo.pk}/",
            {"name": "capa.jpg", "date_taken": "2026-01-02"},
            format="json",
        )

        assert (response.data["name"], response.data["date_taken"]) == ("capa.jpg", "2026-01-02")

    def test_move_goes_last_and_keeps_the_file(self) -> None:
        source = Album.objects.create(name="A")
        target = Album.objects.create(name="B")
        self._photo(target, "existing.jpg", position=0)
        photo = self._photo(source, "moved.jpg")

        response = gallery_manager().patch(
            f"{PHOTOS_URL}{photo.pk}/", {"album_id": target.pk}, format="json"
        )

        photo.refresh_from_db()
        assert response.data["album_id"] == target.pk
        assert (photo.position, photo.image.name) == (1, "gallery/x/moved.jpg")

    def test_image_is_not_accepted(self) -> None:
        photo = self._photo(Album.objects.create(name="Retiros"))

        response = gallery_manager().patch(
            f"{PHOTOS_URL}{photo.pk}/", {"image": "gallery/other.jpg"}, format="json"
        )

        assert response.status_code == 400
        photo.refresh_from_db()
        assert photo.image.name == "gallery/x/a.jpg"

    def test_unknown_photo_is_404(self) -> None:
        response = gallery_manager().patch(f"{PHOTOS_URL}9999/", {"name": "x.jpg"}, format="json")

        assert response.status_code == 404

    def test_unknown_album_is_404(self) -> None:
        photo = self._photo(Album.objects.create(name="Retiros"))

        response = gallery_manager().patch(
            f"{PHOTOS_URL}{photo.pk}/", {"album_id": 9999}, format="json"
        )

        assert response.status_code == 404
