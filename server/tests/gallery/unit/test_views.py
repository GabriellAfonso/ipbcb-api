import pytest
from rest_framework.test import APIClient

from features.gallery.models.gallery import Album, Photo


PHOTOS_URL = "/api/photos/"
ALBUM_PHOTOS_URL = "/api/albums/{album_id}/photos/"


@pytest.mark.django_db
class TestPhotoListAPIView:
    def test_returns_200_with_photos(self) -> None:
        album = Album.objects.create(name="Culto")
        Photo.objects.create(album=album, name="foto1.jpg", image="test1.jpg")
        Photo.objects.create(album=album, name="foto2.jpg", image="test2.jpg")

        client = APIClient()
        response = client.get(PHOTOS_URL)

        assert response.status_code == 200
        assert len(response.data) == 2

    def test_returns_empty_list_when_no_photos(self) -> None:
        client = APIClient()
        response = client.get(PHOTOS_URL)

        assert response.status_code == 200
        assert response.data == []

    def test_response_contains_expected_fields(self) -> None:
        album = Album.objects.create(name="Batismo")
        Photo.objects.create(album=album, name="foto.jpg", image="test.jpg")

        client = APIClient()
        response = client.get(PHOTOS_URL)

        photo_data = response.data[0]
        expected_fields = {
            "id",
            "name",
            "description",
            "album_id",
            "album_name",
            "image_url",
            "date_taken",
            "uploaded_at",
        }
        assert set(photo_data.keys()) == expected_fields

    def test_album_name_is_included(self) -> None:
        album = Album.objects.create(name="Páscoa")
        Photo.objects.create(album=album, name="foto.jpg", image="test.jpg")

        client = APIClient()
        response = client.get(PHOTOS_URL)

        assert response.data[0]["album_name"] == "Páscoa"


@pytest.mark.django_db
class TestAlbumPhotoListAPIView:
    def test_returns_only_photos_from_album(self) -> None:
        album1 = Album.objects.create(name="Album1")
        album2 = Album.objects.create(name="Album2")
        Photo.objects.create(album=album1, name="a1.jpg", image="a1.jpg")
        Photo.objects.create(album=album2, name="a2.jpg", image="a2.jpg")

        client = APIClient()
        response = client.get(ALBUM_PHOTOS_URL.format(album_id=album1.pk))

        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["album_name"] == "Album1"

    def test_returns_empty_list_for_album_with_no_photos(self) -> None:
        album = Album.objects.create(name="Vazio")

        client = APIClient()
        response = client.get(ALBUM_PHOTOS_URL.format(album_id=album.pk))

        assert response.status_code == 200
        assert response.data == []

    def test_returns_empty_for_nonexistent_album(self) -> None:
        client = APIClient()
        response = client.get(ALBUM_PHOTOS_URL.format(album_id=9999))

        assert response.status_code == 200
        assert response.data == []
