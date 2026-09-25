from unittest.mock import MagicMock

import pytest
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.permissions import BasePermission

from core.http.permissions import IsAdminUser, IsMemberUser


def _make_request(user: object | None = None) -> MagicMock:
    request = MagicMock()
    request.user = user
    return request


def _make_user(is_authenticated: bool = True) -> MagicMock:
    user = MagicMock()
    user.is_authenticated = is_authenticated
    user.profile = MagicMock(is_member=False, is_admin=False)
    return user


# ---------------------------------------------------------------------------
# IsMemberUser
# ---------------------------------------------------------------------------


class TestIsMemberUser:
    perm = IsMemberUser()

    def test_member_allowed(self) -> None:
        user = _make_user()
        user.profile.is_member = True
        assert self.perm.has_permission(_make_request(user), MagicMock()) is True

    def test_non_member_denied(self) -> None:
        user = _make_user()
        user.profile.is_member = False
        assert self.perm.has_permission(_make_request(user), MagicMock()) is False

    def test_unauthenticated_denied(self) -> None:
        user = _make_user(is_authenticated=False)
        assert self.perm.has_permission(_make_request(user), MagicMock()) is False


# ---------------------------------------------------------------------------
# IsAdminUser
# ---------------------------------------------------------------------------


class TestIsAdminUser:
    perm = IsAdminUser()

    def test_admin_allowed(self) -> None:
        user = _make_user()
        user.profile.is_admin = True
        assert self.perm.has_permission(_make_request(user), MagicMock()) is True

    def test_non_admin_denied(self) -> None:
        user = _make_user()
        user.profile.is_admin = False
        assert self.perm.has_permission(_make_request(user), MagicMock()) is False

    def test_unauthenticated_denied(self) -> None:
        user = _make_user(is_authenticated=False)
        assert self.perm.has_permission(_make_request(user), MagicMock()) is False


# ---------------------------------------------------------------------------
# User without a Profile row
# ---------------------------------------------------------------------------


class _ProfileDoesNotExist(ObjectDoesNotExist, AttributeError):
    """Same bases as Django's reverse one-to-one ``RelatedObjectDoesNotExist``."""


class FakeUserWithoutProfile:
    """Authenticated user whose ``profile`` access raises, like a user with no row."""

    is_authenticated = True

    @property
    def profile(self) -> object:
        raise _ProfileDoesNotExist("User has no profile.")


class TestUserWithoutProfile:
    """Regression: the permissions evaluated ``request.user.profile`` outside ``getattr``'s
    default, so a user with no Profile row escaped as a 500 instead of a denial."""

    @pytest.mark.parametrize("perm", [IsMemberUser(), IsAdminUser()])
    def test_denied_instead_of_raising(self, perm: BasePermission) -> None:
        request = _make_request(FakeUserWithoutProfile())
        assert perm.has_permission(request, MagicMock()) is False
