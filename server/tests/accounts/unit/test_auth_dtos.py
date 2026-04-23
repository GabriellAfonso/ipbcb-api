import pytest
from pydantic import ValidationError
from features.core.application.dtos.auth_dtos import LoginDTO, RegisterDTO, TokenDTO


def test_register_dto_normalizes_username() -> None:
    dto = RegisterDTO(
        username="  TestUser  ",
        password="secret123",
        first_name="Test",
        last_name="User",
    )
    assert dto.username == "testuser"


def test_register_dto_password_min_length() -> None:
    with pytest.raises(ValidationError):
        RegisterDTO(
            username="testuser",
            password="abc",
            first_name="Test",
            last_name="User",
        )


def test_register_dto_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        RegisterDTO(  # type: ignore[call-arg]
            username="testuser",
            password="secret123",
            first_name="Test",
            last_name="User",
            extra_field="not_allowed",
        )


def test_login_dto_normalizes_username() -> None:
    dto = LoginDTO(username="  ADMIN  ", password="pass")
    assert dto.username == "admin"


def test_token_dto_refresh_is_optional() -> None:
    dto = TokenDTO(access="some.access.token")
    assert dto.access == "some.access.token"
    assert dto.refresh is None
