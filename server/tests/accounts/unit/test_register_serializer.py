import pytest
from features.accounts.serializers.serializers import RegisterSerializer
from features.core.application.dtos.auth_dtos import RegisterDTO

VALID_DATA = {
    "username": "testuser",
    "first_name": "Test",
    "last_name": "User",
    "password": "secret123",
    "password_confirm": "secret123",
}


@pytest.mark.django_db
def test_valid_data_is_valid() -> None:
    s = RegisterSerializer(data=VALID_DATA)
    assert s.is_valid(), s.errors


@pytest.mark.django_db
def test_passwords_mismatch_raises_error() -> None:
    data = {**VALID_DATA, "password_confirm": "differentpass"}
    s = RegisterSerializer(data=data)
    assert not s.is_valid()
    assert "password_confirm" in s.errors


@pytest.mark.django_db
def test_empty_username_raises_error() -> None:
    data = {**VALID_DATA, "username": ""}
    s = RegisterSerializer(data=data)
    assert not s.is_valid()
    assert "username" in s.errors


@pytest.mark.django_db
def test_empty_first_name_raises_error() -> None:
    data = {**VALID_DATA, "first_name": ""}
    s = RegisterSerializer(data=data)
    assert not s.is_valid()
    assert "first_name" in s.errors


@pytest.mark.django_db
def test_empty_last_name_raises_error() -> None:
    data = {**VALID_DATA, "last_name": ""}
    s = RegisterSerializer(data=data)
    assert not s.is_valid()
    assert "last_name" in s.errors


@pytest.mark.django_db
def test_create_dto_returns_register_dto() -> None:
    s = RegisterSerializer(data=VALID_DATA)
    assert s.is_valid()
    dto = s.create_dto()
    assert isinstance(dto, RegisterDTO)
    assert dto.first_name == VALID_DATA["first_name"]
    assert dto.last_name == VALID_DATA["last_name"]
    assert dto.password == VALID_DATA["password"]


@pytest.mark.django_db
def test_create_dto_normalizes_username() -> None:
    data = {**VALID_DATA, "username": "  TestUser  "}
    s = RegisterSerializer(data=data)
    assert s.is_valid(), s.errors
    dto = s.create_dto()
    assert dto.username == "testuser"


@pytest.mark.django_db
def test_password_too_short_raises_error() -> None:
    data = {**VALID_DATA, "password": "abc12", "password_confirm": "abc12"}
    s = RegisterSerializer(data=data)
    assert not s.is_valid()
    assert "password" in s.errors
