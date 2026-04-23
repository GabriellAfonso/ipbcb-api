import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from tests.conftest import make_user

REFRESH_URL = "/api/auth/refresh/"


@pytest.mark.django_db
def test_refresh_valid_token_returns_200() -> None:
    user = make_user(username="refreshuser", password="testpass123")
    refresh = str(RefreshToken.for_user(user))
    client = APIClient()
    response = client.post(REFRESH_URL, {"refresh": refresh}, format="json")
    assert response.status_code == 200
    assert "access" in response.data


@pytest.mark.django_db
def test_refresh_invalid_token_returns_401() -> None:
    client = APIClient()
    response = client.post(REFRESH_URL, {"refresh": "this.is.not.valid"}, format="json")
    assert response.status_code == 401


@pytest.mark.django_db
def test_refresh_rotates_token() -> None:
    user = make_user(username="rotateuser", password="testpass123")
    refresh = str(RefreshToken.for_user(user))
    client = APIClient()
    response = client.post(REFRESH_URL, {"refresh": refresh}, format="json")
    assert response.status_code == 200
    # With ROTATE_REFRESH_TOKENS=True, a new refresh token is returned
    assert "refresh" in response.data
    assert response.data["refresh"] != refresh


@pytest.mark.django_db
def test_refresh_blacklisted_token_returns_401() -> None:
    user = make_user(username="blacklistuser", password="testpass123")
    refresh = str(RefreshToken.for_user(user))
    client = APIClient()
    # First use — valid, blacklists the original token
    response1 = client.post(REFRESH_URL, {"refresh": refresh}, format="json")
    assert response1.status_code == 200
    # Second use of the same token — should be blacklisted
    response2 = client.post(REFRESH_URL, {"refresh": refresh}, format="json")
    assert response2.status_code == 401
