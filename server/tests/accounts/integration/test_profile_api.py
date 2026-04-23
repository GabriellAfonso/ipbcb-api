import io
import tempfile
from typing import IO

import pytest
from django.test import override_settings
from PIL import Image
from rest_framework.test import APIClient

from tests.conftest import make_auth_client, make_user

PROFILE_URL = "/api/me/profile/"
PHOTO_URL = "/api/me/profile/photo/"


def _create_image_file(filename: str = "photo.jpg", fmt: str = "JPEG") -> IO[bytes]:
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color="red").save(buf, format=fmt)
    buf.seek(0)
    buf.name = filename
    return buf


# ---------------------------------------------------------------------------
# GET /api/me/profile/
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_get_profile_returns_200() -> None:
    user = make_user(username="profileuser", password="testpass123")
    client = make_auth_client(user)
    response = client.get(PROFILE_URL)
    assert response.status_code == 200
    assert "name" in response.data


@pytest.mark.django_db
def test_get_profile_unauthenticated_returns_401() -> None:
    client = APIClient()
    response = client.get(PROFILE_URL)
    assert response.status_code == 401


@pytest.mark.django_db
def test_get_profile_returns_etag_header() -> None:
    user = make_user(username="etaguser", password="testpass123")
    client = make_auth_client(user)
    response = client.get(PROFILE_URL)
    assert response.status_code == 200
    assert "ETag" in response


@pytest.mark.django_db
def test_get_profile_returns_304_on_etag_match() -> None:
    user = make_user(username="etagcache", password="testpass123")
    client = make_auth_client(user)

    first = client.get(PROFILE_URL)
    assert first.status_code == 200
    etag = first["ETag"]

    second = client.get(PROFILE_URL, HTTP_IF_NONE_MATCH=etag)
    assert second.status_code == 304


# ---------------------------------------------------------------------------
# PATCH /api/me/profile/
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_patch_profile_updates_name() -> None:
    user = make_user(username="patchuser", password="testpass123")
    client = make_auth_client(user)
    response = client.patch(PROFILE_URL, {"name": "Updated Name"}, format="json")
    assert response.status_code == 200
    assert response.data["name"] == "Updated Name"
    user.profile.refresh_from_db()
    assert user.profile.name == "Updated Name"


@pytest.mark.django_db
def test_patch_profile_cannot_update_is_admin() -> None:
    user = make_user(username="noadmin", password="testpass123")
    client = make_auth_client(user)
    response = client.patch(PROFILE_URL, {"is_admin": True}, format="json")
    assert response.status_code == 200
    user.profile.refresh_from_db()
    assert user.profile.is_admin is False


# ---------------------------------------------------------------------------
# POST /api/me/profile/photo/
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_upload_photo_returns_200() -> None:
    with override_settings(MEDIA_ROOT=tempfile.mkdtemp()):
        user = make_user(username="photouser", password="testpass123")
        client = make_auth_client(user)
        response = client.post(PHOTO_URL, {"photo": _create_image_file()}, format="multipart")
        assert response.status_code == 200
        assert "photo_url" in response.data


@pytest.mark.django_db
def test_upload_photo_replaces_old_photo() -> None:
    with override_settings(MEDIA_ROOT=tempfile.mkdtemp()):
        user = make_user(username="replaceuser", password="testpass123")
        client = make_auth_client(user)

        # First upload
        res1 = client.post(
            PHOTO_URL, {"photo": _create_image_file("first.jpg")}, format="multipart"
        )
        assert res1.status_code == 200
        user.profile.refresh_from_db()
        assert user.profile.photo

        # Second upload — should replace without error; profile must still have a photo
        res2 = client.post(
            PHOTO_URL, {"photo": _create_image_file("second.jpg")}, format="multipart"
        )
        assert res2.status_code == 200
        user.profile.refresh_from_db()
        assert user.profile.photo  # photo still set after replacement


# ---------------------------------------------------------------------------
# DELETE /api/me/profile/photo/
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_delete_photo_returns_204() -> None:
    with override_settings(MEDIA_ROOT=tempfile.mkdtemp()):
        user = make_user(username="delphoto", password="testpass123")
        client = make_auth_client(user)

        # Upload a photo first
        client.post(PHOTO_URL, {"photo": _create_image_file()}, format="multipart")
        user.profile.refresh_from_db()
        assert user.profile.photo

        response = client.delete(PHOTO_URL)
        assert response.status_code == 204
        user.profile.refresh_from_db()
        assert not user.profile.photo


@pytest.mark.django_db
def test_delete_photo_when_no_photo_returns_204() -> None:
    # Profile exists but has no photo: DELETE still returns 204 (no error)
    user = make_user(username="nophoto", password="testpass123")
    client = make_auth_client(user)
    response = client.delete(PHOTO_URL)
    assert response.status_code == 204
