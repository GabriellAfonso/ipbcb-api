import pytest

from core.domain.exceptions import MediaPathRejectedError

from features.media.domain.media_rules import (
    MediaAudience,
    audience_for_folder,
    content_type_for,
    first_segment,
    is_own_profile_file,
    validate_media_path,
)


class TestAudienceForFolder:
    @pytest.mark.parametrize("folder", ["gallery", "profiles"])
    def test_member_folders(self, folder: str) -> None:
        assert audience_for_folder(folder) is MediaAudience.MEMBER

    def test_members_folder_can_view_memberss_only(self) -> None:
        assert audience_for_folder("members") is MediaAudience.MEMBERS_SCOPE

    @pytest.mark.parametrize("folder", ["reports", "gallery-old", "Gallery", "", "logo.png"])
    def test_unruled_folders_have_no_audience(self, folder: str) -> None:
        assert audience_for_folder(folder) is None


class TestContentTypeFor:
    @pytest.mark.parametrize(
        "path,expected",
        [
            ("gallery/a/x.jpg", "image/jpeg"),
            ("gallery/a/x.JPG", "image/jpeg"),
            ("gallery/a/x.jpeg", "image/jpeg"),
            ("profiles/u/abc.png", "image/png"),
            ("profiles/u/abc.webp", "image/webp"),
            ("gallery/a/x.gif", "image/gif"),
        ],
    )
    def test_allow_listed_image_formats(self, path: str, expected: str) -> None:
        assert content_type_for(path) == expected

    @pytest.mark.parametrize(
        "path", ["gallery/a/x.html", "gallery/a/x.svg", "gallery/a/noext", "gallery/a/x.jpg.html"]
    )
    def test_everything_else_is_octet_stream(self, path: str) -> None:
        # nginx would guess text/html from the extension; a polyglot must never render.
        assert content_type_for(path) == "application/octet-stream"


class TestValidateMediaPathAccepts:
    @pytest.mark.parametrize(
        "path",
        [
            "gallery/retiro-2025/IMG_0042.jpg",
            "profiles/ana.paula/6f1c2d.png",
            "gallery/ceia-de-natal/Ceia_ção.jpg",
        ],
    )
    def test_valid_paths_are_returned_unchanged(self, path: str) -> None:
        assert validate_media_path(path) == path


class TestFirstSegment:
    def test_returns_folder(self) -> None:
        assert first_segment("gallery/retiro/x.jpg") == "gallery"


class TestValidateMediaPathRejects:
    @pytest.mark.parametrize(
        "path",
        [
            "",
            "/etc/passwd",
            "gallery",
            "gallery/",
            "gallery//x.jpg",
            "gallery/./x.jpg",
            "gallery/../members/x.jpg",
            "gallery/../../config/settings/base.py",
            "../x",
            r"gallery\..\..\x",
            "gallery/%2e%2e/x",
            "gallery/x%00.jpg",
            "gallery/x\x00.jpg",
            "gallery/x\n.jpg",
            "gallery/x\x7f.jpg",
        ],
    )
    def test_rejected(self, path: str) -> None:
        with pytest.raises(MediaPathRejectedError):
            validate_media_path(path)


class TestIsOwnProfileFile:
    def test_file_in_own_folder_is_owned(self) -> None:
        assert is_own_profile_file("profiles/ana.paula/6f1c2d.png", "ana.paula") is True

    @pytest.mark.parametrize(
        "path,own_folder",
        [
            ("profiles/joao/6f1c2d.png", "ana.paula"),  # another user's folder
            ("profiles/ana.paula", "ana.paula"),  # the folder itself, not a file
            ("gallery/ana.paula/x.jpg", "ana.paula"),  # same name, other root folder
            ("members/ana.paula/x.jpg", "ana.paula"),  # never unlocks members/ files
            ("profiles/ana.paula/6f1c2d.png", None),  # caller without a folder
        ],
    )
    def test_anything_else_is_not_owned(self, path: str, own_folder: str | None) -> None:
        assert is_own_profile_file(path, own_folder) is False
