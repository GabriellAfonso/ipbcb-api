import pytest
from rest_framework.test import APIClient
from features.accounts.models.profile import Profile
from features.accounts.models.user import User

REGISTER_URL = "/api/auth/register/"

VALID_PAYLOAD = {
    "username": "newuser",
    "first_name": "New",
    "last_name": "User",
    "password": "securepass",
    "password_confirm": "securepass",
}


@pytest.mark.django_db
def test_register_success_returns_201_with_tokens() -> None:
    client = APIClient()
    response = client.post(REGISTER_URL, VALID_PAYLOAD, format="json")
    assert response.status_code == 201
    assert "access" in response.data
    assert "refresh" in response.data


@pytest.mark.django_db
def test_register_creates_user_in_db() -> None:
    client = APIClient()
    client.post(REGISTER_URL, VALID_PAYLOAD, format="json")
    assert User.objects.filter(username="newuser").exists()


@pytest.mark.django_db
def test_register_creates_profile_via_signal() -> None:
    client = APIClient()
    client.post(REGISTER_URL, VALID_PAYLOAD, format="json")
    user = User.objects.get(username="newuser")
    assert Profile.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_register_duplicate_username_returns_400() -> None:
    User.objects.create_user(username="newuser", password="pass123")
    client = APIClient()
    response = client.post(REGISTER_URL, VALID_PAYLOAD, format="json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_register_passwords_mismatch_returns_400() -> None:
    client = APIClient()
    payload = {**VALID_PAYLOAD, "password_confirm": "wrongpass"}
    response = client.post(REGISTER_URL, payload, format="json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_register_missing_fields_returns_400() -> None:
    client = APIClient()
    response = client.post(REGISTER_URL, {"username": "incomplete"}, format="json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_register_username_is_case_insensitive() -> None:
    client = APIClient()
    payload = {**VALID_PAYLOAD, "username": "  NewUser  "}
    client.post(REGISTER_URL, payload, format="json")
    assert User.objects.filter(username="newuser").exists()
