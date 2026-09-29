import re
from unittest.mock import Mock

import pytest

from features.gallery.models.gallery import (
    Album,
    Photo,
    cover_upload_path,
    photo_upload_path,
    thumbnail_upload_path,
)

_HEX = "[0-9a-f]{32}"


@pytest.mark.django_db
class TestAlbumStr:
    def test_returns_name(self) -> None:
        album = Album.objects.create(name="Culto Especial")
        assert str(album) == "Culto Especial"


@pytest.mark.django_db
class TestPhotoStr:
    def test_returns_name(self) -> None:
        album = Album.objects.create(name="Batismo")
        photo = Photo.objects.create(album=album, name="foto1.jpg", image="test.jpg")
        assert str(photo) == "foto1.jpg"


class TestUploadPaths:
    """Fallbacks for files saved straight through a field; the album name never appears, so a
    rename never leaves a folder named after the old name."""

    def test_photo_path_uses_the_album_id_and_a_random_name(self) -> None:
        instance = Mock(album_id=7)
        assert re.fullmatch(rf"gallery/7/{_HEX}\.png", photo_upload_path(instance, "My Photo.PNG"))

    def test_thumbnail_path(self) -> None:
        instance = Mock(album_id=7)
        assert re.fullmatch(rf"gallery/thumbs/7/{_HEX}\.jpg", thumbnail_upload_path(instance, "x"))

    def test_cover_path(self) -> None:
        instance = Mock(pk=9)
        assert re.fullmatch(rf"gallery/covers/9/{_HEX}\.jpg", cover_upload_path(instance, "x"))
