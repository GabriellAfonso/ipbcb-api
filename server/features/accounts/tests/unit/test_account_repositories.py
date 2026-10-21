"""UserRepository.set_password/delete and RefreshTokenRepository (specs/021-user-account)."""

import pytest
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from conftest import make_user
from features.accounts.models.user import User
from features.accounts.repositories.refresh_token_repository import RefreshTokenRepositoryImpl
from features.accounts.repositories.user_repository import UserRepositoryImpl

pytestmark = pytest.mark.django_db


def test_set_password_stores_the_new_hash() -> None:
    user = make_user(username="ana", password="secret1")
    UserRepositoryImpl().set_password(user, "new-secret")
    user.refresh_from_db()
    assert user.check_password("new-secret")
    assert not user.check_password("secret1")


def test_delete_removes_the_user_and_its_profile() -> None:
    user = make_user(username="ana")
    UserRepositoryImpl().delete(user)
    assert not User.objects.filter(username="ana").exists()


class TestRevokeAll:
    def test_blacklists_every_live_token_of_the_user(self) -> None:
        user = make_user(username="ana")
        RefreshToken.for_user(user)
        RefreshToken.for_user(user)

        revoked = RefreshTokenRepositoryImpl().revoke_all(user.pk)

        assert revoked == 2
        assert BlacklistedToken.objects.filter(token__user=user).count() == 2

    def test_is_idempotent(self) -> None:
        user = make_user(username="ana")
        RefreshToken.for_user(user)
        repo = RefreshTokenRepositoryImpl()
        repo.revoke_all(user.pk)

        assert repo.revoke_all(user.pk) == 0
        assert BlacklistedToken.objects.count() == 1

    def test_leaves_other_users_alone(self) -> None:
        ana, bia = make_user(username="ana"), make_user(username="bia")
        RefreshToken.for_user(ana)
        RefreshToken.for_user(bia)

        RefreshTokenRepositoryImpl().revoke_all(ana.pk)

        assert not BlacklistedToken.objects.filter(token__user=bia).exists()
        assert OutstandingToken.objects.filter(user=bia).count() == 1
