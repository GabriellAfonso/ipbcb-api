import pytest
from pydantic import ValidationError
from features.core.application.dtos.auth_dtos import LoginDTO, RegisterDTO, TokenDTO


def test_register_dto_normalizes_username():
    dto = RegisterDTO(
        username="  TestUser  ",
        password="secret123",
        first_name="Test",
        last_name="User",
    )
    assert dto.username == "testuser"


def test_register_dto_password_min_length():
    with pytest.raises(ValidationError):
        RegisterDTO(
            username="testuser",
            password="abc",
            first_name="Test",
            last_name="User",
        )


def test_register_dto_extra_fields_forbidden():
    with pytest.raises(ValidationError):
        RegisterDTO(
            username="testuser",
            password="secret123",
            first_name="Test",
            last_name="User",
            extra_field="not_allowed",
        )


def test_login_dto_normalizes_username():
    dto = LoginDTO(username="  ADMIN  ", password="pass")
    assert dto.username == "admin"


def test_token_dto_refresh_is_optional():
    dto = TokenDTO(access="some.access.token")
    assert dto.access == "some.access.token"
    assert dto.refresh is None
