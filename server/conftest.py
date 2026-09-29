import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.domain.access import Role
from features.accounts.models.user import User


def make_user(username: str = "testuser", password: str = "testpass123", **kwargs: str) -> User:  # nosec B107
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


def make_role_client(*roles: Role, username: str = "role_user") -> tuple[APIClient, User]:
    """Return (client, user) for a user holding ``roles``. The groups are seeded by migration
    ``core.0005_seed_panel_roles``, so they exist in every test database.

    >>> client, user = make_role_client(Role.LEADER, Role.MEDIA, username="both")
    """
    user = make_user(username=username, password="rolepass123")  # nosec B106
    user.groups.add(*Group.objects.filter(name__in=[role.value for role in roles]))
    return make_auth_client(user), user


def make_admin_client() -> tuple[APIClient, User]:
    """Return (client, user) for an Admin role holder."""
    return make_role_client(Role.ADMIN, username="admin_user")


def make_member_client() -> tuple[APIClient, User]:
    """Return (client, user) for a member user."""
    user = make_user(username="member_user", password="memberpass123")  # nosec B106
    user.profile.is_member = True
    user.profile.save()
    return make_auth_client(user), user


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()
