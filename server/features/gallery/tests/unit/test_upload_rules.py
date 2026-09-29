import pytest

from core.domain.exceptions import ClientUploadNeedsOneFileError, InvalidClientUploadIdError
from features.gallery.domain.upload_rules import (
    CLIENT_UPLOAD_ID_MAX_LENGTH,
    CLIENT_UPLOAD_ID_SHAPE,
    ensure_valid_client_upload,
)

UUID_V4 = "3f2a9c1e-7b4d-4e8a-9f10-2c6b5d7e8a90"


class TestValidIds:
    @pytest.mark.parametrize(
        "client_upload_id",
        [UUID_V4, UUID_V4.upper(), "a", "x" * CLIENT_UPLOAD_ID_MAX_LENGTH, "abc_DEF-123"],
    )
    def test_accepted_with_one_file(self, client_upload_id: str) -> None:
        ensure_valid_client_upload(client_upload_id, 1)


class TestInvalidIds:
    def test_empty_value(self) -> None:
        with pytest.raises(InvalidClientUploadIdError, match="empty"):
            ensure_valid_client_upload("", 1)

    def test_too_long_names_the_length_and_echoes_only_the_limit(self) -> None:
        with pytest.raises(InvalidClientUploadIdError) as caught:
            ensure_valid_client_upload("x" * 65, 1)

        assert "got 65 characters" in str(caught.value)
        assert caught.value.client_upload_id == "x" * CLIENT_UPLOAD_ID_MAX_LENGTH
        assert caught.value.expected == CLIENT_UPLOAD_ID_SHAPE

    @pytest.mark.parametrize(
        ("client_upload_id", "fragment"),
        [
            ("abc def", "' ' at position 3"),
            ("é", "'é' at position 0"),
            ("a/b", "'/'"),
            ("a.b", "'.'"),
        ],
    )
    def test_bad_character_names_it_and_its_position(
        self, client_upload_id: str, fragment: str
    ) -> None:
        with pytest.raises(InvalidClientUploadIdError) as caught:
            ensure_valid_client_upload(client_upload_id, 1)

        assert fragment in str(caught.value)
        assert CLIENT_UPLOAD_ID_SHAPE in str(caught.value)

    def test_shape_is_checked_before_the_file_count(self) -> None:
        with pytest.raises(InvalidClientUploadIdError):
            ensure_valid_client_upload("", 3)


class TestFileCount:
    @pytest.mark.parametrize("file_count", [0, 2, 5])
    def test_anything_but_one_file_is_refused(self, file_count: int) -> None:
        with pytest.raises(ClientUploadNeedsOneFileError) as caught:
            ensure_valid_client_upload(UUID_V4, file_count)

        assert caught.value.file_count == file_count
        assert f"got {file_count}" in str(caught.value)
