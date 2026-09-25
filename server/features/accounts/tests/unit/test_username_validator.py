"""The username is also a directory name, so the rules are narrower than Django's."""

import pytest
from django.core.exceptions import ValidationError as DjangoValidationError

from features.accounts.validators import (
    is_valid_username,
    profile_photo_folder,
    sanitize_username,
    validate_username,
)


class TestAcceptedUsernames:
    @pytest.mark.parametrize(
        "username",
        ["gabriel", "ana.paula", "jose_silva", "pastor-joao", "joao123", "a", "a1"],
    )
    def test_accepts_ordinary_names(self, username: str) -> None:
        assert is_valid_username(username) is True


class TestRejectedUsernames:
    @pytest.mark.parametrize(
        ("username", "reason"),
        [
            ("a/b/c", "path separator would become a directory"),
            ("..", "parent directory raises SuspiciousFileOperation on save"),
            (".", "current directory"),
            (".hidden", "leading dot"),
            ("trailing.", "trailing dot"),
            ("foo bar", "space"),
            ("admin​", "zero-width space impersonating 'admin'"),
            ("аdmin", "Cyrillic homoglyph impersonating 'admin'"),
            ("joão", "accented letter — not ASCII"),
            ("ADMIN", "uppercase: validation runs after normalisation"),
            ("", "empty"),
        ],
    )
    def test_rejects_unsafe_names(self, username: str, reason: str) -> None:
        assert is_valid_username(username) is False, reason

    def test_django_default_validator_would_have_allowed_double_dot(self) -> None:
        """Why this module exists: UnicodeUsernameValidator accepts '..' — we must not."""
        from django.contrib.auth.validators import UnicodeUsernameValidator

        UnicodeUsernameValidator()("..")  # does not raise

        assert is_valid_username("..") is False


class TestValidateUsername:
    def test_passes_silently_for_a_valid_name(self) -> None:
        validate_username("ana.paula")

    def test_raises_with_the_offending_value(self) -> None:
        with pytest.raises(DjangoValidationError, match="a/b"):
            validate_username("a/b")


class TestSanitizeUsername:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("João.Silva", "joao.silva"),
            ("maria+igreja", "maria-igreja"),
            ("foo/bar", "foo-bar"),
            ("...", "usuario"),
            ("", "usuario"),
            ("Ana", "ana"),
        ],
    )
    def test_produces_a_valid_username(self, raw: str, expected: str) -> None:
        result = sanitize_username(raw)

        assert result == expected
        assert is_valid_username(result) is True

    def test_transliterates_accents_instead_of_dropping_them(self) -> None:
        """'joão' must become 'joao', not 'joo'."""
        assert sanitize_username("joão") == "joao"


class TestProfilePhotoFolder:
    def test_valid_username_is_the_folder(self) -> None:
        assert profile_photo_folder("ana.paula", "3f2b") == "ana.paula"

    @pytest.mark.parametrize("legacy_username", ["Ana Paula", "../admin", "a/b"])
    def test_legacy_username_falls_back_to_user_id(self, legacy_username: str) -> None:
        assert profile_photo_folder(legacy_username, "3f2b") == "3f2b"
