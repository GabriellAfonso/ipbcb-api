from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from core.application.dtos.auth_dtos import TokenDTO
from core.domain.exceptions import (
    GoogleUserCreationError,
    InvalidGoogleTokenError,
    UnverifiedGoogleEmailError,
)
from features.accounts.services.google_auth_service import GoogleAuthService
from features.accounts.tests.fakes import FakeAvatarDownloader


FAKE_IDINFO = {
    "email": "user@gmail.com",
    "email_verified": True,
    "given_name": "Test",
    "family_name": "User",
    "picture": "https://photo.google.com/photo=s96-c",
}

FAKE_TOKEN_DTO = TokenDTO(access="fake-access", refresh="fake-refresh")


@pytest.fixture
def mock_user_repo() -> MagicMock:
    repo = MagicMock()
    repo.get_by_email.return_value = None
    repo.generate_unique_username.return_value = "user"
    return repo


@pytest.fixture
def mock_profile_repo() -> MagicMock:
    repo = MagicMock()
    profile = MagicMock()
    profile.photo = None
    repo.get_or_create.return_value = (profile, True)
    return repo


@pytest.fixture
def avatar_downloader() -> FakeAvatarDownloader:
    return FakeAvatarDownloader(content=None)


@pytest.fixture
def service(
    mock_user_repo: MagicMock,
    mock_profile_repo: MagicMock,
    avatar_downloader: FakeAvatarDownloader,
) -> GoogleAuthService:
    return GoogleAuthService(
        user_repository=mock_user_repo,
        profile_repository=mock_profile_repo,
        avatar_downloader=avatar_downloader,
    )


def _png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (10, 10)).save(buffer, format="PNG")
    return buffer.getvalue()


@patch(
    "features.accounts.services.google_auth_service.get_tokens_for_user",
    return_value=FAKE_TOKEN_DTO,
)
@patch("features.accounts.services.google_auth_service.id_token.verify_oauth2_token")
def test_authenticate_new_user(
    mock_verify: MagicMock,
    mock_get_tokens: MagicMock,
    service: GoogleAuthService,
    mock_user_repo: MagicMock,
) -> None:
    mock_verify.return_value = FAKE_IDINFO
    mock_user_repo.create_google_user.return_value = MagicMock(username="user")

    result = service.authenticate_google("fake-token")

    assert isinstance(result, TokenDTO)
    assert result.access == "fake-access"
    mock_user_repo.get_by_email.assert_called_once_with("user@gmail.com")
    mock_user_repo.create_google_user.assert_called_once()


@patch(
    "features.accounts.services.google_auth_service.get_tokens_for_user",
    return_value=FAKE_TOKEN_DTO,
)
@patch("features.accounts.services.google_auth_service.id_token.verify_oauth2_token")
def test_authenticate_existing_user(
    mock_verify: MagicMock,
    mock_get_tokens: MagicMock,
    service: GoogleAuthService,
    mock_user_repo: MagicMock,
    mock_profile_repo: MagicMock,
) -> None:
    mock_verify.return_value = FAKE_IDINFO
    existing_user = MagicMock(username="existing")
    mock_user_repo.get_by_email.return_value = existing_user

    # Profile already has photo
    profile = MagicMock()
    profile.photo = "existing.jpg"
    mock_profile_repo.get_or_create.return_value = (profile, False)

    result = service.authenticate_google("fake-token")

    assert isinstance(result, TokenDTO)
    mock_user_repo.create_google_user.assert_not_called()


@patch("features.accounts.services.google_auth_service.id_token.verify_oauth2_token")
def test_invalid_token_raises(mock_verify: MagicMock, service: GoogleAuthService) -> None:
    mock_verify.side_effect = ValueError("bad token")

    with pytest.raises(InvalidGoogleTokenError):
        service.authenticate_google("bad-token")


@patch("features.accounts.services.google_auth_service.id_token.verify_oauth2_token")
def test_unverified_email_raises(mock_verify: MagicMock, service: GoogleAuthService) -> None:
    mock_verify.return_value = {**FAKE_IDINFO, "email_verified": False}

    with pytest.raises(UnverifiedGoogleEmailError):
        service.authenticate_google("fake-token")


@patch("features.accounts.services.google_auth_service.id_token.verify_oauth2_token")
def test_empty_email_raises(mock_verify: MagicMock, service: GoogleAuthService) -> None:
    mock_verify.return_value = {**FAKE_IDINFO, "email": "", "email_verified": True}

    with pytest.raises(UnverifiedGoogleEmailError):
        service.authenticate_google("fake-token")


@patch("features.accounts.services.google_auth_service.id_token.verify_oauth2_token")
def test_user_creation_failure_raises(
    mock_verify: MagicMock, service: GoogleAuthService, mock_user_repo: MagicMock
) -> None:
    mock_verify.return_value = FAKE_IDINFO
    mock_user_repo.create_google_user.side_effect = GoogleUserCreationError("user@gmail.com")

    with pytest.raises(GoogleUserCreationError):
        service.authenticate_google("fake-token")


@patch("features.accounts.services.google_auth_service.id_token.verify_oauth2_token")
def test_unexpected_creation_error_is_not_disguised(
    mock_verify: MagicMock, service: GoogleAuthService, mock_user_repo: MagicMock
) -> None:
    """Regression: an `except Exception` used to turn every bug into "Erro ao criar usuário"."""
    mock_verify.return_value = FAKE_IDINFO
    mock_user_repo.create_google_user.side_effect = RuntimeError("bug")

    with pytest.raises(RuntimeError, match="bug"):
        service.authenticate_google("fake-token")


@patch(
    "features.accounts.services.google_auth_service.get_tokens_for_user",
    return_value=FAKE_TOKEN_DTO,
)
@patch("features.accounts.services.google_auth_service.id_token.verify_oauth2_token")
def test_avatar_is_requested_at_400px_and_saved(
    mock_verify: MagicMock,
    mock_get_tokens: MagicMock,
    service: GoogleAuthService,
    mock_profile_repo: MagicMock,
    avatar_downloader: FakeAvatarDownloader,
) -> None:
    mock_verify.return_value = FAKE_IDINFO
    avatar_downloader.content = _png_bytes()

    service.authenticate_google("fake-token")

    assert avatar_downloader.requested_urls == ["https://photo.google.com/photo=s400-c"]
    assert mock_profile_repo.save_photo.call_args[0][1] == "png"


@patch(
    "features.accounts.services.google_auth_service.get_tokens_for_user",
    return_value=FAKE_TOKEN_DTO,
)
@patch("features.accounts.services.google_auth_service.id_token.verify_oauth2_token")
def test_failed_avatar_download_saves_nothing_and_logs_in(
    mock_verify: MagicMock,
    mock_get_tokens: MagicMock,
    service: GoogleAuthService,
    mock_profile_repo: MagicMock,
) -> None:
    mock_verify.return_value = FAKE_IDINFO

    result = service.authenticate_google("fake-token")

    assert result == FAKE_TOKEN_DTO
    mock_profile_repo.save_photo.assert_not_called()


@patch(
    "features.accounts.services.google_auth_service.get_tokens_for_user",
    return_value=FAKE_TOKEN_DTO,
)
@patch("features.accounts.services.google_auth_service.id_token.verify_oauth2_token")
def test_non_image_avatar_saves_nothing_and_logs_in(
    mock_verify: MagicMock,
    mock_get_tokens: MagicMock,
    service: GoogleAuthService,
    mock_profile_repo: MagicMock,
    avatar_downloader: FakeAvatarDownloader,
) -> None:
    mock_verify.return_value = FAKE_IDINFO
    avatar_downloader.content = b"<html>not an image</html>"

    result = service.authenticate_google("fake-token")

    assert result == FAKE_TOKEN_DTO
    mock_profile_repo.save_photo.assert_not_called()
