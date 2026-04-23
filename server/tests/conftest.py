import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from features.accounts.models.user import User


def make_user(username: str = "testuser", password: str = "testpass123", **kwargs: str) -> User:
    """Create a User. A Profile is auto-created via signal."""
    return User.objects.create_user(username=username, password=password, **kwargs)


def get_access_token(user: User) -> str:
    return str(RefreshToken.for_user(user).access_token)


def get_refresh_token(user: User) -> str:
    return str(RefreshToken.for_user(user))


def make_auth_client(user: User) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_access_token(user)}")
    return client


def make_admin_client() -> tuple[APIClient, User]:
    """Return (client, user) for an admin user."""
    user = make_user(username="admin_user", password="adminpass123")
    user.profile.is_admin = True
    user.profile.save()
    return make_auth_client(user), user


def make_member_client() -> tuple[APIClient, User]:
    """Return (client, user) for a member user."""
    user = make_user(username="member_user", password="memberpass123")
    user.profile.is_member = True
    user.profile.save()
    return make_auth_client(user), user


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()
