import pytest
from unittest.mock import Mock

from features.gallery.models.gallery import Album, Photo, photo_upload_path


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


class TestPhotoUploadPath:
    def test_generates_path_with_slugified_album(self) -> None:
        instance = Mock()
        instance.album.name = "Culto Especial"
        result = photo_upload_path(instance, "photo.jpg")
        assert result == "gallery/culto-especial/photo.jpg"

    def test_handles_accented_album_name(self) -> None:
        instance = Mock()
        instance.album.name = "Celebração de Páscoa"
        result = photo_upload_path(instance, "img.png")
        assert result == "gallery/celebracao-de-pascoa/img.png"

    def test_preserves_filename(self) -> None:
        instance = Mock()
        instance.album.name = "Test"
        result = photo_upload_path(instance, "my photo (1).jpg")
        assert result == "gallery/test/my photo (1).jpg"
