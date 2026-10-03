import pytest
from typing import Any
from unittest.mock import patch
from dependency_injector import providers
from rest_framework.test import APIClient
from config.di import Container
from features.accounts.models.user import User
from features.accounts.tests.fakes import FakeAvatarDownloader
from conftest import make_user

GOOGLE_URL = "/api/auth/google/"
MOCK_PATH = "features.accounts.services.google_auth_service.id_token.verify_oauth2_token"


def _google_payload(
    email: str = "user@example.com",
    given_name: str = "Test",
    family_name: str = "User",
    picture: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "email": email,
        "email_verified": True,
        "given_name": given_name,
        "family_name": family_name,
    }
    if picture:
        payload["picture"] = picture
    return payload


@pytest.mark.django_db
def test_google_login_creates_new_user() -> None:
    client = APIClient()
    with patch(MOCK_PATH, return_value=_google_payload(email="newgoogle@example.com")):
        response = client.post(GOOGLE_URL, {"id_token": "fake_token"}, format="json")
    assert response.status_code == 200
    assert "access" in response.data
    assert User.objects.filter(email="newgoogle@example.com").exists()


@pytest.mark.django_db
def test_google_login_existing_user_returns_tokens() -> None:
    make_user(username="googleuser", password="pass123", email="exists@example.com")
    user_count_before = User.objects.count()

    client = APIClient()
    with patch(MOCK_PATH, return_value=_google_payload(email="exists@example.com")):
        response = client.post(GOOGLE_URL, {"id_token": "fake_token"}, format="json")

    assert response.status_code == 200
    assert "access" in response.data
    assert User.objects.count() == user_count_before


@pytest.mark.django_db
def test_google_login_invalid_token_returns_401() -> None:
    client = APIClient()
    with patch(MOCK_PATH, side_effect=ValueError("bad token")):
        response = client.post(GOOGLE_URL, {"id_token": "invalid_token"}, format="json")
    assert response.status_code == 401


@pytest.mark.django_db
def test_google_login_missing_token_returns_400() -> None:
    client = APIClient()
    response = client.post(GOOGLE_URL, {}, format="json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_google_login_generates_unique_username() -> None:
    # "john" is already taken, so google login with john@example.com should use "john1"
    make_user(username="john", email="other@example.com", password="pass123")

    client = APIClient()
    with patch(MOCK_PATH, return_value=_google_payload(email="john@example.com")):
        response = client.post(GOOGLE_URL, {"id_token": "fake_token"}, format="json")

    assert response.status_code == 200
    new_user = User.objects.get(email="john@example.com")
    assert new_user.username == "john1"


@pytest.mark.django_db
def test_google_login_empty_email_returns_400() -> None:
    client = APIClient()
    with patch(MOCK_PATH, return_value=_google_payload(email="")):
        response = client.post(GOOGLE_URL, {"id_token": "fake_token"}, format="json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_google_login_photo_download_failure_still_succeeds(di_container: Container) -> None:
    """Photo download fails gracefully — user still created, tokens returned."""
    client = APIClient()
    payload = _google_payload(email="photofail@example.com", picture="https://example.com/pic.jpg")
    failing_download = FakeAvatarDownloader(content=None)
    with (
        patch(MOCK_PATH, return_value=payload),
        di_container.avatar_downloader.override(providers.Object(failing_download)),
    ):
        response = client.post(GOOGLE_URL, {"id_token": "fake_token"}, format="json")
    assert response.status_code == 200
    assert "access" in response.data
    assert User.objects.filter(email="photofail@example.com").exists()
    assert failing_download.requested_urls == ["https://example.com/pic.jpg=s400-c"]


@pytest.mark.django_db
def test_google_login_creation_clash_returns_500_without_partial_user() -> None:
    """Two first logins racing: the loser's insert hits a unique column. The repository turns
    the IntegrityError into GoogleUserCreationError, and nothing half-created is left."""
    make_user(username="racer", password="pass123", email="other@example.com")
    client = APIClient()
    with (
        patch(MOCK_PATH, return_value=_google_payload(email="racer@example.com")),
        # Simulates the race: the username was free when generated, taken at insert time.
        patch(
            "features.accounts.repositories.user_repository.UserRepositoryImpl"
            ".generate_unique_username",
            return_value="racer",
        ),
    ):
        response = client.post(GOOGLE_URL, {"id_token": "fake_token"}, format="json")
    assert response.status_code == 500
    assert response.data["error_code"] == "DOMAIN_ERROR"
    assert not User.objects.filter(email="racer@example.com").exists()


@pytest.mark.django_db
def test_google_login_existing_user_with_photo_not_overwritten() -> None:
    """If user already has a profile photo, Google photo should NOT overwrite it."""
    import tempfile
    from django.core.files.base import ContentFile
    from django.test import override_settings

    with override_settings(MEDIA_ROOT=tempfile.mkdtemp()):
        user = make_user(username="haspic", password="pass123", email="haspic@example.com")
        user.profile.photo.save("existing.jpg", ContentFile(b"existing-photo"), save=True)

        client = APIClient()
        payload = _google_payload(email="haspic@example.com", picture="https://example.com/pic.jpg")
        with patch(MOCK_PATH, return_value=payload):
            response = client.post(GOOGLE_URL, {"id_token": "fake_token"}, format="json")

        assert response.status_code == 200
        user.profile.refresh_from_db()
        # Photo should still exist (Google login doesn't overwrite existing photos)
        assert user.profile.photo, "Existing photo should not be removed"
