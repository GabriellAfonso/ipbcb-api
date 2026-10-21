"""POST api/me/delete/ end to end (specs/021-user-account US1, contracts/account-api.md)."""

import json

import io
import tempfile
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest
from axes.models import AccessAttempt
from django.test import override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.response import Response
from rest_framework.test import APIClient

from conftest import get_refresh_token, link_to_ministry, make_auth_client, make_user
from core.models.device_token import DeviceToken
from features.accounts.models.profile import Profile
from features.accounts.models.user import User
from features.events.models.event import Event
from features.members.models.member import Member
from features.members.models.member_change_log import MemberChangeLog
from features.songs.models.setlist import Setlist

DELETE_URL = "/api/me/delete/"
REFRESH_URL = "/api/auth/refresh/"
VERIFY_PATH = "features.accounts.services.google_auth_service.id_token.verify_oauth2_token"

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def media_root() -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as root, override_settings(MEDIA_ROOT=root):
        yield Path(root)


@pytest.fixture(autouse=True)
def clear_attempts() -> Iterator[None]:
    yield
    AccessAttempt.objects.all().delete()


def _google_only(username: str = "gabi", email: str = "gabi@gmail.com") -> User:
    user = make_user(username=username, email=email)
    user.set_unusable_password()
    user.save()
    return user


def _google_payload(email: str) -> dict[str, object]:
    return {"email": email, "email_verified": True, "given_name": "G", "family_name": "B"}


def _give_photo(user: User) -> Path:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), color="red").save(buffer, format="PNG")
    buffer.seek(0)
    response = make_auth_client(user).post(
        "/api/me/profile/photo/", {"photo": buffer}, format="multipart"
    )
    assert response.status_code == 200
    user.profile.refresh_from_db()
    return Path(user.profile.photo.path)


def _delete(client: APIClient, **body: str) -> Response:
    response: Response = client.post(DELETE_URL, body, format="json")
    return response


class TestPasswordAccount:
    def test_deletes_everything_personal(self) -> None:
        user = make_user(username="ana", password="secret1")
        photo = _give_photo(user)
        DeviceToken.objects.create(token="fcm-ana", user=user)
        refresh = get_refresh_token(user)

        response = _delete(make_auth_client(user), password="secret1")

        assert response.status_code == 204
        assert not User.objects.filter(username="ana").exists()
        assert not Profile.objects.filter(user_id=user.pk).exists()
        assert not DeviceToken.objects.exists()
        assert not photo.exists()
        assert APIClient().post(REFRESH_URL, {"refresh": refresh}, format="json").status_code == 401

    def test_keeps_the_roll_and_authored_content(self) -> None:
        user = make_user(username="ana", password="secret1")
        member = link_to_ministry(user)
        log = MemberChangeLog.objects.create(member=member, editor=user, field="name")
        event = Event.objects.create(
            title="Retiro", start_date=date(2026, 11, 1), image_path="events/x.jpg", created_by=user
        )
        setlist = Setlist.objects.create(
            date=date(2026, 11, 1), saved_by=user, saved_at=timezone.now()
        )

        assert _delete(make_auth_client(user), password="secret1").status_code == 204

        assert Member.objects.filter(pk=member.pk).exists()
        for row, field in ((log, "editor_id"), (event, "created_by_id"), (setlist, "saved_by_id")):
            row.refresh_from_db()
            assert getattr(row, field) is None

    def test_wrong_password_is_400_and_keeps_the_account(self) -> None:
        user = make_user(username="ana", password="secret1")
        response = _delete(make_auth_client(user), password="wrong!")
        assert response.status_code == 400
        assert response.data["error_code"] == "INVALID_PASSWORD"
        assert User.objects.filter(pk=user.pk).exists()

    def test_missing_password_names_the_method(self) -> None:
        user = make_user(username="ana", password="secret1")
        response = _delete(make_auth_client(user), id_token="google-token")
        assert response.status_code == 400
        assert response.data["error_code"] == "VALIDATION_ERROR"
        assert response.data["detail"] == "Esta conta tem senha: confirme com a senha."

    @override_settings(AXES_ENABLED=True)
    def test_lockout_after_five_wrong_passwords(self) -> None:
        user = make_user(username="ana", password="secret1")
        client = make_auth_client(user)
        for _ in range(5):
            _delete(client, password="wrong!")
        response = _delete(client, password="secret1")
        assert response.status_code == 429
        assert json.loads(response.content)["error_code"] == "ACCOUNT_LOCKED"
        assert User.objects.filter(pk=user.pk).exists()

    def test_retry_after_success_is_unauthenticated(self) -> None:
        user = make_user(username="ana", password="secret1")
        client = make_auth_client(user)
        _delete(client, password="secret1")
        assert _delete(client, password="secret1").status_code == 401


class TestGoogleOnlyAccount:
    def test_token_of_the_same_account_deletes(self) -> None:
        user = _google_only()
        with patch(VERIFY_PATH, return_value=_google_payload("gabi@gmail.com")):
            response = _delete(make_auth_client(user), id_token="google-token")
        assert response.status_code == 204
        assert not User.objects.filter(pk=user.pk).exists()

    def test_token_of_another_account_is_403(self) -> None:
        user = _google_only()
        make_user(username="other", email="other@gmail.com")
        with patch(VERIFY_PATH, return_value=_google_payload("other@gmail.com")):
            response = _delete(make_auth_client(user), id_token="google-token")
        assert response.status_code == 403
        assert response.data["error_code"] == "GOOGLE_ACCOUNT_MISMATCH"
        assert User.objects.filter(pk=user.pk).exists()

    def test_invalid_token_is_400(self) -> None:
        user = _google_only()
        with patch(VERIFY_PATH, side_effect=ValueError("expired")):
            response = _delete(make_auth_client(user), id_token="google-token")
        assert response.status_code == 400
        assert response.data["error_code"] == "INVALID_GOOGLE_TOKEN"

    def test_password_is_refused(self) -> None:
        user = _google_only()
        response = _delete(make_auth_client(user), password="secret1")
        assert response.status_code == 400
        assert response.data["detail"] == "Esta conta não tem senha: confirme com o Google."


def test_superuser_is_blocked() -> None:
    user = make_user(username="root", password="secret1")
    user.is_superuser = True
    user.save()
    response = _delete(make_auth_client(user), password="secret1")
    assert response.status_code == 409
    assert response.data["error_code"] == "ACCOUNT_DELETION_BLOCKED"
    assert User.objects.filter(pk=user.pk).exists()


def test_requires_authentication() -> None:
    assert _delete(APIClient(), password="secret1").status_code == 401


def test_body_must_be_an_object() -> None:
    user = make_user(username="ana", password="secret1")
    response = make_auth_client(user).post(DELETE_URL, ["secret1"], format="json")
    assert response.status_code == 400
