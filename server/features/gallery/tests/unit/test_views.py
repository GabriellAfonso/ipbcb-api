import pytest
from rest_framework.test import APIClient

from conftest import make_auth_client, make_member_client, make_user
from features.gallery.models.gallery import Album, Photo

PHOTOS_URL = "/api/photos/"
ALBUM_PHOTOS_URL = "/api/albums/{album_id}/photos/"


@pytest.mark.django_db
class TestPhotoListAPIViewPermissions:
    def test_unauthenticated_returns_401(self) -> None:
        assert APIClient().get(PHOTOS_URL).status_code == 401

    def test_non_member_returns_403(self) -> None:
        client = make_auth_client(make_user(username="regular"))
        assert client.get(PHOTOS_URL).status_code == 403

    def test_member_returns_200(self) -> None:
        client, _ = make_member_client()
        assert client.get(PHOTOS_URL).status_code == 200


@pytest.mark.django_db
class TestPhotoListAPIView:
    def test_returns_200_with_photos(self) -> None:
        album = Album.objects.create(name="Culto")
        Photo.objects.create(album=album, name="foto1.jpg", image="test1.jpg")
        Photo.objects.create(album=album, name="foto2.jpg", image="test2.jpg")

        client, _ = make_member_client()
        response = client.get(PHOTOS_URL)

        assert response.status_code == 200
        assert len(response.data) == 2

    def test_returns_empty_list_when_no_photos(self) -> None:
        client, _ = make_member_client()
        response = client.get(PHOTOS_URL)

        assert response.status_code == 200
        assert response.data == []

    def test_album_name_is_included(self) -> None:
        album = Album.objects.create(name="Páscoa")
        Photo.objects.create(album=album, name="foto.jpg", image="test.jpg")

        client, _ = make_member_client()
        assert client.get(PHOTOS_URL).data[0]["album_name"] == "Páscoa"

    def test_order_follows_the_album_tree_then_position(self) -> None:
        second_root = Album.objects.create(name="A", position=1)
        first_root = Album.objects.create(name="B", position=0)
        Photo.objects.create(album=second_root, name="a.jpg", image="a.jpg")
        Photo.objects.create(album=first_root, name="b2.jpg", image="b2.jpg", position=1)
        Photo.objects.create(album=first_root, name="b1.jpg", image="b1.jpg", position=0)

        client, _ = make_member_client()
        names = [photo["name"] for photo in client.get(PHOTOS_URL).data]

        assert names == ["b1.jpg", "b2.jpg", "a.jpg"]


@pytest.mark.django_db
class TestAlbumPhotoListAPIViewPermissions:
    def test_unauthenticated_returns_401(self) -> None:
        album = Album.objects.create(name="Test")
        assert APIClient().get(ALBUM_PHOTOS_URL.format(album_id=album.pk)).status_code == 401

    def test_non_member_returns_403(self) -> None:
        album = Album.objects.create(name="Test")
        client = make_auth_client(make_user(username="regular2"))
        assert client.get(ALBUM_PHOTOS_URL.format(album_id=album.pk)).status_code == 403


@pytest.mark.django_db
class TestAlbumPhotoListAPIView:
    def test_returns_only_photos_directly_in_the_album(self) -> None:
        album = Album.objects.create(name="Album1")
        child = Album.objects.create(name="Sub", parent=album)
        Photo.objects.create(album=album, name="a1.jpg", image="a1.jpg")
        Photo.objects.create(album=child, name="sub.jpg", image="sub.jpg")

        client, _ = make_member_client()
        response = client.get(ALBUM_PHOTOS_URL.format(album_id=album.pk))

        assert response.status_code == 200
        assert [photo["name"] for photo in response.data] == ["a1.jpg"]

    def test_returns_empty_list_for_album_with_no_photos(self) -> None:
        album = Album.objects.create(name="Vazio")

        client, _ = make_member_client()
        response = client.get(ALBUM_PHOTOS_URL.format(album_id=album.pk))

        assert response.status_code == 200
        assert response.data == []

    def test_nonexistent_album_is_404(self) -> None:
        client, _ = make_member_client()
        response = client.get(ALBUM_PHOTOS_URL.format(album_id=9999))

        assert response.status_code == 404
        assert response.data["error_code"] == "NOT_FOUND"
