"""``POST /api/photos/`` with ``client_upload_id``, with real files in a temporary MEDIA_ROOT
(specs/016-photo-upload-idempotency US1–US4; contracts/photo-upload-api.md)."""

from pathlib import Path
from unittest.mock import patch

import pytest
from rest_framework.response import Response
from rest_framework.test import APIClient

from conftest import make_member_client
from features.gallery.models.gallery import Album, Photo
from features.gallery.repositories.gallery_repository import GalleryRepositoryImpl
from features.gallery.tests.integration.helpers import gallery_manager, image_file, text_file

PHOTOS_URL = "/api/photos/"
UPLOAD_ID = "3f2a9c1e-7b4d-4e8a-9f10-2c6b5d7e8a90"
PHOTO_KEYS = {
    "id",
    "name",
    "description",
    "album_id",
    "album_name",
    "image_url",
    "thumbnail_url",
    "date_taken",
    "uploaded_at",
    "position",
    "members",
}


def _upload(
    client: APIClient, album_id: int, client_upload_id: object = UPLOAD_ID, **extra: object
) -> Response:
    body: dict[str, object] = {"album_id": album_id, "image": image_file(), **extra}
    if client_upload_id is not None:
        body["client_upload_id"] = client_upload_id
    response: Response = client.post(PHOTOS_URL, body, format="multipart")
    return response


def _stored_files(media_root: Path) -> set[Path]:
    return {path for path in media_root.rglob("*") if path.is_file()}


@pytest.mark.django_db
@pytest.mark.usefixtures("media_root")
class TestRetry:
    def test_same_id_twice_is_201_twice_with_one_photo(self, media_root: Path) -> None:
        client = gallery_manager()
        album = Album.objects.create(name="Retiro 2026")
        first = _upload(client, album.pk)
        files_after_first = _stored_files(media_root)

        second = _upload(client, album.pk)

        assert (first.status_code, second.status_code) == (201, 201)
        assert second.data["accepted"][0]["id"] == first.data["accepted"][0]["id"]
        assert second.data["rejected"] == []
        listed = client.get(f"/api/albums/{album.pk}/photos/").data
        assert [photo["id"] for photo in listed] == [first.data["accepted"][0]["id"]]
        assert _stored_files(media_root) == files_after_first

    def test_resource_never_carries_the_id(self) -> None:
        client = gallery_manager()
        album = Album.objects.create(name="Retiro 2026")

        responses = [_upload(client, album.pk), _upload(client, album.pk)]

        for response in responses:
            assert set(response.data["accepted"][0]) == PHOTO_KEYS
        assert UPLOAD_ID not in str(client.get(PHOTOS_URL).data)

    def test_moved_photo_comes_back_in_its_new_album(self) -> None:
        client = gallery_manager()
        album, other = Album.objects.create(name="A"), Album.objects.create(name="B")
        photo_id = _upload(client, album.pk).data["accepted"][0]["id"]
        client.patch(f"/api/photos/{photo_id}/", {"album_id": other.pk}, format="json")

        response = _upload(client, album.pk)

        assert response.status_code == 201
        assert response.data["accepted"][0]["album_id"] == other.pk

    def test_unknown_album_on_a_retry_is_not_a_404(self) -> None:
        client = gallery_manager()
        album = Album.objects.create(name="Retiro 2026")
        photo_id = _upload(client, album.pk).data["accepted"][0]["id"]

        response = _upload(client, 999_999)

        assert response.status_code == 201
        assert response.data["accepted"][0]["id"] == photo_id

    def test_invalid_file_on_a_retry_is_not_examined(self) -> None:
        client = gallery_manager()
        album = Album.objects.create(name="Retiro 2026")
        photo_id = _upload(client, album.pk).data["accepted"][0]["id"]

        response = client.post(
            PHOTOS_URL,
            {"album_id": album.pk, "image": text_file(), "client_upload_id": UPLOAD_ID},
            format="multipart",
        )

        assert response.status_code == 201
        assert response.data["accepted"][0]["id"] == photo_id


@pytest.mark.django_db
@pytest.mark.usefixtures("media_root")
class TestRetryAfterDelete:
    def test_trashed_original_is_409_without_the_photo(self) -> None:
        client = gallery_manager()
        album = Album.objects.create(name="Retiro 2026")
        photo_id = _upload(client, album.pk).data["accepted"][0]["id"]
        assert client.delete(f"/api/photos/{photo_id}/").status_code == 204

        response = _upload(client, album.pk)

        assert response.status_code == 409
        assert response.data["error_code"] == "CONFLICT"
        assert "lixeira" in response.data["detail"]
        assert response.data["client_upload_id"] == UPLOAD_ID
        assert "photo_id" not in response.data
        assert Photo.all_objects.count() == 1 and not Photo.objects.exists()

    def test_restored_original_is_returned_again(self) -> None:
        client = gallery_manager()
        album = Album.objects.create(name="Retiro 2026")
        photo_id = _upload(client, album.pk).data["accepted"][0]["id"]
        client.delete(f"/api/photos/{photo_id}/")
        client.post(f"/api/gallery/trash/photos/{photo_id}/restore/")

        response = _upload(client, album.pk)

        assert response.status_code == 201
        assert response.data["accepted"][0]["id"] == photo_id


@pytest.mark.django_db
@pytest.mark.usefixtures("media_root")
class TestLostRace:
    def test_constraint_decides_and_the_loser_leaves_no_file(self, media_root: Path) -> None:
        """The fast-path lookup misses once, as when the winner commits between the loser's
        lookup and its insert (specs/016 research R-10; the real race is quickstart §3)."""
        client = gallery_manager()
        album = Album.objects.create(name="Retiro 2026")
        winner_id = _upload(client, album.pk).data["accepted"][0]["id"]
        files_before = _stored_files(media_root)
        real_lookup = GalleryRepositoryImpl.find_client_upload
        calls: list[str] = []

        def miss_once(repository: GalleryRepositoryImpl, client_upload_id: str) -> object:
            calls.append(client_upload_id)
            return None if len(calls) == 1 else real_lookup(repository, client_upload_id)

        with patch.object(GalleryRepositoryImpl, "find_client_upload", miss_once):
            response = _upload(client, album.pk)

        assert response.status_code == 201
        assert response.data["accepted"][0]["id"] == winner_id
        assert Photo.all_objects.filter(client_upload_id=UPLOAD_ID).count() == 1
        assert _stored_files(media_root) == files_before


@pytest.mark.django_db
@pytest.mark.usefixtures("media_root")
class TestWithoutId:
    def test_same_file_twice_makes_two_photos(self) -> None:
        client = gallery_manager()
        album = Album.objects.create(name="Retiro 2026")

        _upload(client, album.pk, client_upload_id=None)
        _upload(client, album.pk, client_upload_id=None)

        assert Photo.objects.count() == 2
        assert not Photo.objects.filter(client_upload_id__isnull=False).exists()

    def test_multi_file_upload_is_unchanged(self) -> None:
        client = gallery_manager()
        album = Album.objects.create(name="Retiro 2026")

        response = client.post(
            PHOTOS_URL,
            {"album_id": album.pk, "image": [image_file("a.jpg"), text_file("b.jpg")]},
            format="multipart",
        )

        assert response.status_code == 207
        assert len(response.data["accepted"]) == 1

    def test_photo_without_id_never_matches_a_later_id(self) -> None:
        client = gallery_manager()
        album = Album.objects.create(name="Retiro 2026")
        _upload(client, album.pk, client_upload_id=None)

        response = _upload(client, album.pk)

        assert response.status_code == 201
        assert Photo.objects.count() == 2


@pytest.mark.django_db
@pytest.mark.usefixtures("media_root")
class TestMalformed:
    @pytest.mark.parametrize("bad", ["x" * 65, "", "com espaço", "ç"])
    def test_bad_id_is_400_naming_the_field_and_shape(self, bad: str) -> None:
        album = Album.objects.create(name="Retiro 2026")

        response = _upload(gallery_manager(), album.pk, client_upload_id=bad)

        assert response.status_code == 400
        assert response.data["error_code"] == "VALIDATION_ERROR"
        assert "client_upload_id" in response.data["detail"]
        assert response.data["client_upload_id"] == bad[:64]
        assert "A-Z" in response.data["expected"]
        assert not Photo.all_objects.exists()

    def test_id_with_two_files_is_400_with_the_count(self, media_root: Path) -> None:
        album = Album.objects.create(name="Retiro 2026")

        response = gallery_manager().post(
            PHOTOS_URL,
            {
                "album_id": album.pk,
                "image": [image_file("a.jpg"), image_file("b.jpg")],
                "client_upload_id": UPLOAD_ID,
            },
            format="multipart",
        )

        assert response.status_code == 400
        assert response.data["file_count"] == 2
        assert not Photo.all_objects.exists() and _stored_files(media_root) == set()

    def test_id_sent_twice_is_400_naming_it(self) -> None:
        album = Album.objects.create(name="Retiro 2026")

        response = _upload(gallery_manager(), album.pk, client_upload_id=[UPLOAD_ID, "other"])

        assert response.status_code == 400
        assert "'client_upload_id'" in response.data["detail"]
        assert not Photo.all_objects.exists()

    def test_missing_album_id_keeps_the_existing_400(self) -> None:
        response = gallery_manager().post(
            PHOTOS_URL, {"image": image_file(), "client_upload_id": UPLOAD_ID}, format="multipart"
        )

        assert response.status_code == 400
        assert "album_id" in response.data["detail"]

    def test_member_without_manage_is_403_before_the_id_is_read(self) -> None:
        album = Album.objects.create(name="Retiro 2026")
        client, _ = make_member_client()

        response = _upload(client, album.pk, client_upload_id="")

        assert response.status_code == 403
