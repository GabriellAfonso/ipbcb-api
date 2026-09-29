"""The Django admin upload page goes through the same service as ``POST /api/photos/``
(specs/013-gallery-write-api FR-019a)."""

import io
import re
from pathlib import Path
from unittest.mock import PropertyMock, patch

import pytest
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.test import Client
from PIL import Image

from core.files.image_validation import MAX_IMAGE_BYTES
from features.accounts.models.user import User
from features.gallery.models.gallery import Album, Photo
from features.gallery.tests.support import stored_name

UPLOAD_URL = "/admin/gallery/album/upload/"


def _make_image_file(name: str = "test.jpg", fmt: str = "JPEG") -> io.BytesIO:
    buf = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buf, format=fmt)
    buf.seek(0)
    buf.name = name
    return buf


@pytest.mark.django_db
@pytest.mark.usefixtures("media_root")
class TestUploadPhotosView:
    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        self.client = Client()
        self.user = User.objects.create_superuser(username="admin_upload", password="adminpass123")
        self.client.force_login(self.user)
        self.album = Album.objects.create(name="Upload Test")

    def test_get_returns_html_form_with_album_paths(self) -> None:
        Album.objects.create(name="2026", parent=self.album)

        response = self.client.get(UPLOAD_URL)

        assert response.status_code == 200
        assert b"<form" in response.content
        assert "Upload Test / 2026".encode() in response.content

    def test_post_valid_upload_stores_like_the_api(self) -> None:
        response = self.client.post(
            UPLOAD_URL, {"album": self.album.pk, "images": _make_image_file()}
        )

        assert response.status_code == 302
        photo = Photo.objects.get(album=self.album)
        assert re.fullmatch(
            rf"gallery/{self.album.pk}/[0-9a-f]{{32}}\.jpg", stored_name(photo.image)
        )
        assert stored_name(photo.thumbnail).startswith(f"gallery/thumbs/{self.album.pk}/")
        assert (photo.uploaded_by_id, photo.position, photo.name) == (self.user.pk, 0, "test.jpg")
        # The page never sends a retry key (specs/016-photo-upload-idempotency FR-016).
        assert photo.client_upload_id is None

    def test_first_upload_gives_the_album_its_cover(self, media_root: Path) -> None:
        self.client.post(UPLOAD_URL, {"album": self.album.pk, "images": _make_image_file()})

        self.album.refresh_from_db()
        assert stored_name(self.album.cover_image).startswith(f"gallery/covers/{self.album.pk}/")
        assert (media_root / stored_name(self.album.cover_image)).exists()

    def test_post_without_album_returns_error(self) -> None:
        response = self.client.post(UPLOAD_URL, {"images": _make_image_file()})

        assert response.status_code == 200
        assert b"Selecione" in response.content

    def test_post_without_files_returns_error(self) -> None:
        response = self.client.post(UPLOAD_URL, {"album": self.album.pk})

        assert response.status_code == 200
        assert b"Selecione" in response.content

    def test_unknown_album(self) -> None:
        response = self.client.post(UPLOAD_URL, {"album": 9999, "images": _make_image_file()})

        assert "Álbum não encontrado".encode() in response.content

    def test_post_oversized_file_returns_error(self) -> None:
        oversized = InMemoryUploadedFile(
            file=_make_image_file(),
            field_name="images",
            name="big.jpg",
            content_type="image/jpeg",
            size=MAX_IMAGE_BYTES + 1,
            charset=None,
        )

        with patch.object(
            type(oversized), "size", new_callable=PropertyMock, return_value=MAX_IMAGE_BYTES + 1
        ):
            response = self.client.post(UPLOAD_URL, {"album": self.album.pk, "images": oversized})

        assert response.status_code == 200
        assert b"big.jpg: " in response.content
        assert b"muito grande" in response.content
        assert Photo.objects.count() == 0

    def test_partial_upload_keeps_the_valid_file_and_lists_the_bad_one(self) -> None:
        bad = io.BytesIO(b"not-an-image")
        bad.name = "bad.jpg"

        response = self.client.post(
            UPLOAD_URL, {"album": self.album.pk, "images": [_make_image_file("ok.jpg"), bad]}
        )

        assert response.status_code == 200
        assert b"bad.jpg: " in response.content
        assert b"formato" in response.content.lower()
        assert Photo.objects.count() == 1
