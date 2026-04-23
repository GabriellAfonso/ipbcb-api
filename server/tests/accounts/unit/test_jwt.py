import pytest
from features.accounts.auth.jwt import get_tokens_for_user
from features.core.application.dtos.auth_dtos import TokenDTO
from tests.conftest import make_user


@pytest.mark.django_db
def test_get_tokens_for_user_returns_token_dto() -> None:
    user = make_user(username="jwtuser", password="testpass123")
    result = get_tokens_for_user(user)
    assert isinstance(result, TokenDTO)


@pytest.mark.django_db
def test_tokens_contain_access_and_refresh() -> None:
    user = make_user(username="jwtuser2", password="testpass123")
    result = get_tokens_for_user(user)
    assert isinstance(result.access, str) and len(result.access) > 0
    assert isinstance(result.refresh, str) and len(result.refresh) > 0
