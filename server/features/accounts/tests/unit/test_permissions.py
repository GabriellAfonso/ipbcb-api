from unittest.mock import MagicMock

import pytest
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.permissions import BasePermission

from core.application.dtos.access_dtos import AccessGrantsDTO
from core.domain.access import Role
from core.http import permissions as permissions_module
from core.http.permissions import HasMemberAccess


class FakeGrants:
    """Stands in for ``_grants_for``: answers fixed roles and records who was asked."""

    def __init__(self, roles: list[Role]) -> None:
        self.roles = roles
        self.calls = 0

    def __call__(self, user_id: object) -> AccessGrantsDTO:
        self.calls += 1
        return AccessGrantsDTO(roles=self.roles, levels={})


@pytest.fixture
def no_roles(monkeypatch: pytest.MonkeyPatch) -> FakeGrants:
    fake = FakeGrants([])
    monkeypatch.setattr(permissions_module, "_grants_for", fake)
    return fake


def _make_request(user: object | None = None) -> MagicMock:
    request = MagicMock()
    request.user = user
    return request


def _make_user(is_authenticated: bool = True) -> MagicMock:
    user = MagicMock()
    user.is_authenticated = is_authenticated
    user.profile = MagicMock(member_access=False)
    return user


# ---------------------------------------------------------------------------
# HasMemberAccess
# ---------------------------------------------------------------------------


class TestHasMemberAccess:
    perm = HasMemberAccess()

    def test_flag_allows_without_reading_roles(self, no_roles: FakeGrants) -> None:
        user = _make_user()
        user.profile.member_access = True
        assert self.perm.has_permission(_make_request(user), MagicMock()) is True
        assert no_roles.calls == 0

    def test_no_flag_no_role_denied(self, no_roles: FakeGrants) -> None:
        user = _make_user()
        user.profile.member_access = False
        assert self.perm.has_permission(_make_request(user), MagicMock()) is False

    @pytest.mark.parametrize(
        ("roles", "allowed"),
        [([Role.ADMIN], True), ([Role.LEADER], True), ([Role.MEDIA], False)],
    )
    def test_leadership_roles_allow_without_flag(
        self, monkeypatch: pytest.MonkeyPatch, roles: list[Role], allowed: bool
    ) -> None:
        monkeypatch.setattr(permissions_module, "_grants_for", FakeGrants(roles))
        assert self.perm.has_permission(_make_request(_make_user()), MagicMock()) is allowed

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
    pk = "no-profile-user"

    @property
    def profile(self) -> object:
        raise _ProfileDoesNotExist("User has no profile.")


class TestUserWithoutProfile:
    """Regression: the permissions evaluated ``request.user.profile`` outside ``getattr``'s
    default, so a user with no Profile row escaped as a 500 instead of a denial."""

    @pytest.mark.parametrize("perm", [HasMemberAccess()])
    def test_denied_instead_of_raising(self, perm: BasePermission, no_roles: FakeGrants) -> None:
        request = _make_request(FakeUserWithoutProfile())
        assert perm.has_permission(request, MagicMock()) is False
