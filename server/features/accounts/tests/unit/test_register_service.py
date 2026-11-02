import pytest
from unittest.mock import MagicMock, patch

from core.application.dtos.auth_dtos import RegisterDTO, TokenDTO
from core.domain.exceptions import UsernameAlreadyExistsError
from features.accounts.services.register_service import RegisterService

FAKE_TOKEN_DTO = TokenDTO(access="fake-access", refresh="fake-refresh")


@pytest.fixture
def mock_user_repo() -> MagicMock:
    return MagicMock()


@pytest.fixture
def service(mock_user_repo: MagicMock) -> RegisterService:
    return RegisterService(user_repository=mock_user_repo)


@pytest.fixture
def sample_dto() -> RegisterDTO:
    return RegisterDTO(
        username="newuser",
        password="securepass123",
        first_name="New",
        last_name="User",
        recovery_email="new@example.com",
    )


@patch(
    "features.accounts.services.register_service.get_tokens_for_user",
    return_value=FAKE_TOKEN_DTO,
)
def test_register_success(
    mock_get_tokens: MagicMock,
    service: RegisterService,
    mock_user_repo: MagicMock,
    sample_dto: RegisterDTO,
) -> None:
    mock_user_repo.username_exists.return_value = False
    mock_user_repo.create.return_value = MagicMock()

    result = service.register(sample_dto)

    assert isinstance(result, TokenDTO)
    assert result.access == "fake-access"
    mock_user_repo.username_exists.assert_called_once_with("newuser")
    mock_user_repo.create.assert_called_once_with(sample_dto)
    mock_get_tokens.assert_called_once()


def test_register_duplicate_username_raises(
    service: RegisterService, mock_user_repo: MagicMock, sample_dto: RegisterDTO
) -> None:
    mock_user_repo.username_exists.return_value = True

    with pytest.raises(UsernameAlreadyExistsError) as exc_info:
        service.register(sample_dto)

    assert "newuser" in str(exc_info.value)
    mock_user_repo.create.assert_not_called()
