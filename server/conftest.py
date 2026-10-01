from typing import TYPE_CHECKING

import pytest
from django.apps import apps as django_apps
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.domain.access import Role
from features.accounts.apps import AccountsConfig
from features.accounts.models.user import User
from features.members.models.member import Member, Ministry

if TYPE_CHECKING:
    from config.di import Container


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


def link_to_ministry(user: User, ministry_name: str = "Louvor", **member_fields: object) -> Member:
    """Link ``user``'s profile to a new roll member in ``ministry_name`` (created if missing).
    "Louvor" makes the user a worship member (specs/017-sunday-setlist-push).

    >>> link_to_ministry(make_user(username="ana")).ministries.get().name
    'Louvor'
    """
    ministry, _ = Ministry.objects.get_or_create(name=ministry_name)
    member = Member.objects.create(name=user.username, **member_fields)
    member.ministries.add(ministry)
    user.profile.member = member
    user.profile.save()
    return member


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def di_container() -> "Container":
    """The wired DI container the views resolve from. Override a provider on it with
    ``with di_container.push_sender.override(providers.Object(fake)):`` — overriding the
    ``Container`` class does not reach this instance."""
    config = django_apps.get_app_config("accounts")
    assert isinstance(config, AccountsConfig)
    return config.container
