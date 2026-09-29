import io
import tempfile
from typing import IO

import pytest
from django.contrib.auth.models import Group
from django.test import override_settings
from PIL import Image
from rest_framework.test import APIClient

from conftest import make_auth_client, make_role_client, make_user
from core.domain.access import Role

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
def test_is_admin_is_gone_and_cannot_grant_a_role() -> None:
    # specs/012-feature-role-permissions FR-021: the flag was replaced by roles.
    user = make_user(username="noadmin", password="testpass123")
    client = make_auth_client(user)
    response = client.patch(PROFILE_URL, {"is_admin": True}, format="json")
    assert response.status_code == 200
    assert "is_admin" not in response.data
    assert response.data["roles"] == []
    assert not user.groups.exists()


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


# ---------------------------------------------------------------------------
# Panel roles and levels (specs/012-feature-role-permissions/contracts/profile-api.md)
# ---------------------------------------------------------------------------

ALL_SCOPES = [
    "members",
    "schedule",
    "songs",
    "gallery",
    "events",
    "notices",
    "reports.hymnal_history",
]
LEADER_PERMISSIONS = {
    "members": "manage",
    "schedule": "manage",
    "songs": "manage",
    "gallery": "owner",
    "events": "manage",
    "notices": "manage",
    "reports.hymnal_history": "view",
}


@pytest.mark.django_db
class TestProfileRoles:
    def test_leader(self) -> None:
        client, _ = make_role_client(Role.LEADER)
        data = client.get(PROFILE_URL).data
        assert data["roles"] == [{"id": "leader", "name": "Liderança"}]
        assert data["permissions"] == LEADER_PERMISSIONS

    def test_admin_owns_everything(self) -> None:
        client, _ = make_role_client(Role.ADMIN)
        data = client.get(PROFILE_URL).data
        assert data["roles"] == [{"id": "admin", "name": "Admin"}]
        assert data["permissions"] == {scope: "owner" for scope in ALL_SCOPES}

    def test_no_role(self) -> None:
        client, _ = make_role_client()
        data = client.get(PROFILE_URL).data
        assert data["roles"] == []
        assert data["permissions"] == {scope: None for scope in ALL_SCOPES}

    def test_two_roles_give_the_higher_level(self) -> None:
        client, _ = make_role_client(Role.MEDIA, Role.LEADER)
        data = client.get(PROFILE_URL).data
        assert [role["id"] for role in data["roles"]] == ["leader", "media"]
        assert data["permissions"] == LEADER_PERMISSIONS

    def test_superuser_without_role_has_nothing(self) -> None:
        client, user = make_role_client()
        user.is_superuser = True
        user.is_staff = True
        user.save()
        data = client.get(PROFILE_URL).data
        assert data["roles"] == []
        assert set(data["permissions"].values()) == {None}

    def test_patch_returns_roles_and_ignores_them(self) -> None:
        client, _ = make_role_client(Role.MEDIA)
        response = client.patch(
            PROFILE_URL,
            {"name": "Nova", "roles": [{"id": "admin"}], "permissions": {"members": "owner"}},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["roles"] == [{"id": "media", "name": "Mídia"}]
        assert response.data["permissions"]["members"] is None

    def test_role_change_invalidates_the_etag(self) -> None:
        client, user = make_role_client()
        etag = client.get(PROFILE_URL)["ETag"]
        user.groups.add(Group.objects.get(name=Role.LEADER.value))
        response = client.get(PROFILE_URL, HTTP_IF_NONE_MATCH=etag)
        assert response.status_code == 200
