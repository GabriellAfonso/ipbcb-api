import pytest
from rest_framework.test import APIClient
from tests.conftest import make_user

LOGIN_URL = "/api/auth/login/"


@pytest.mark.django_db
def test_login_success_returns_200_with_tokens() -> None:
    make_user(username="loginuser", password="mypassword")
    client = APIClient()
    response = client.post(
        LOGIN_URL,
        {"username": "loginuser", "password": "mypassword"},
        format="json",
    )
    assert response.status_code == 200
    assert "access" in response.data
    assert "refresh" in response.data


@pytest.mark.django_db
def test_login_wrong_password_returns_401() -> None:
    make_user(username="loginuser", password="mypassword")
    client = APIClient()
    response = client.post(
        LOGIN_URL,
        {"username": "loginuser", "password": "wrongpass"},
        format="json",
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_login_nonexistent_user_returns_401() -> None:
    client = APIClient()
    response = client.post(
        LOGIN_URL,
        {"username": "nobody", "password": "somepass"},
        format="json",
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_login_inactive_user_returns_401() -> None:
    user = make_user(username="inactiveuser", password="mypassword")
    user.is_active = False
    user.save()
    client = APIClient()
    response = client.post(
        LOGIN_URL,
        {"username": "inactiveuser", "password": "mypassword"},
        format="json",
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_login_missing_fields_returns_400() -> None:
    client = APIClient()
    # LoginDTO raises pydantic.ValidationError → LoginAPI returns 401
    response = client.post(LOGIN_URL, {}, format="json")
    assert response.status_code == 401
