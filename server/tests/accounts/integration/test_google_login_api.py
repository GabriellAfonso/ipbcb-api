import pytest
from unittest.mock import patch
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from tests.conftest import make_user

User = get_user_model()

GOOGLE_URL = "/api/auth/google/"
MOCK_PATH = "features.accounts.views.auth.id_token.verify_oauth2_token"


def _google_payload(email="user@example.com", given_name="Test", family_name="User", picture=None):
    payload = {"email": email, "given_name": given_name, "family_name": family_name}
    if picture:
        payload["picture"] = picture
    return payload


@pytest.mark.django_db
def test_google_login_creates_new_user():
    client = APIClient()
    with patch(MOCK_PATH, return_value=_google_payload(email="newgoogle@example.com")):
        response = client.post(GOOGLE_URL, {"id_token": "fake_token"}, format="json")
    assert response.status_code == 200
    assert "access" in response.data
    assert User.objects.filter(email="newgoogle@example.com").exists()


@pytest.mark.django_db
def test_google_login_existing_user_returns_tokens():
    make_user(username="googleuser", password="pass123", email="exists@example.com")
    user_count_before = User.objects.count()

    client = APIClient()
    with patch(MOCK_PATH, return_value=_google_payload(email="exists@example.com")):
        response = client.post(GOOGLE_URL, {"id_token": "fake_token"}, format="json")

    assert response.status_code == 200
    assert "access" in response.data
    assert User.objects.count() == user_count_before


@pytest.mark.django_db
def test_google_login_invalid_token_returns_401():
    client = APIClient()
    with patch(MOCK_PATH, side_effect=ValueError("bad token")):
        response = client.post(GOOGLE_URL, {"id_token": "invalid_token"}, format="json")
    assert response.status_code == 401


@pytest.mark.django_db
def test_google_login_missing_token_returns_400():
    client = APIClient()
    response = client.post(GOOGLE_URL, {}, format="json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_google_login_generates_unique_username():
    # "john" is already taken, so google login with john@example.com should use "john1"
    make_user(username="john", email="other@example.com", password="pass123")

    client = APIClient()
    with patch(MOCK_PATH, return_value=_google_payload(email="john@example.com")):
        response = client.post(GOOGLE_URL, {"id_token": "fake_token"}, format="json")

    assert response.status_code == 200
    new_user = User.objects.get(email="john@example.com")
    assert new_user.username == "john1"
