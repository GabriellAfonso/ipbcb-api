from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

import pytest
from django.http import FileResponse, HttpResponse
from pytest_django.fixtures import SettingsWrapper
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from conftest import make_admin_client, make_auth_client, make_member_client, make_user
from features.media.tests.integration.conftest import GALLERY_BYTES, GALLERY_FILE, media_url

WriteMedia = Callable[..., Path]


# ---------------------------------------------------------------------------
# US1 — a leaked media URL is useless without an account
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestUnauthenticated:
    def test_anonymous_gets_401_without_file_or_redirect(self, write_media: WriteMedia) -> None:
        write_media(GALLERY_FILE)
        response = APIClient().get(media_url(GALLERY_FILE))
        assert response.status_code == 401
        assert response.data["error_code"] == "NOT_AUTHENTICATED"
        assert "X-Accel-Redirect" not in response
        assert GALLERY_BYTES not in response.content

    def test_malformed_token_gets_401(self, write_media: WriteMedia) -> None:
        write_media(GALLERY_FILE)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer not-a-jwt")
        response = client.get(media_url(GALLERY_FILE))
        assert response.status_code == 401
        assert response.data["error_code"] == "AUTHENTICATION_FAILED"

    def test_expired_token_gets_401(self, write_media: WriteMedia) -> None:
        write_media(GALLERY_FILE)
        token = AccessToken.for_user(make_user(username="expired"))
        token.set_exp(lifetime=-timedelta(minutes=1))
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        assert client.get(media_url(GALLERY_FILE)).status_code == 401

    def test_anonymous_cannot_tell_missing_from_existing(self, media_root: Path) -> None:
        response = APIClient().get(media_url("gallery/nope/missing.jpg"))
        assert response.status_code == 401

    def test_empty_media_path_goes_through_the_check(self, media_root: Path) -> None:
        response = APIClient().get("/ipbcb/media/")
        assert response.status_code == 401
        assert response.data["error_code"] == "NOT_AUTHENTICATED"


@pytest.mark.django_db
class TestMethods:
    def test_post_is_not_allowed(self, write_media: WriteMedia) -> None:
        write_media(GALLERY_FILE)
        client, _ = make_member_client()
        assert client.post(media_url(GALLERY_FILE)).status_code == 405


# ---------------------------------------------------------------------------
# US2 — members keep seeing gallery and profile photos
# ---------------------------------------------------------------------------

PROFILE_FILE = "profiles/ana.paula/6f1c2d0e9a8b.png"


def _assert_accel_redirect(response: HttpResponse, relative_path: str, content_type: str) -> None:
    assert response.status_code == 200
    assert response.content == b""
    assert response["X-Accel-Redirect"] == f"/ipbcb/protected-media/{relative_path}"
    assert response["Cache-Control"] == "private, no-cache"
    assert response["Content-Type"] == content_type
    # Validators come from nginx; here they would describe the empty body.
    assert "ETag" not in response
    assert "Last-Modified" not in response
    assert "Authorization" not in response.get("Vary", "")


@pytest.mark.django_db
class TestMemberAccess:
    def test_member_gets_redirect_to_gallery_file(self, write_media: WriteMedia) -> None:
        write_media(GALLERY_FILE)
        client, _ = make_member_client()
        response = client.get(media_url(GALLERY_FILE))
        _assert_accel_redirect(response, GALLERY_FILE, "image/jpeg")

    def test_member_gets_another_members_profile_photo(self, write_media: WriteMedia) -> None:
        write_media(PROFILE_FILE)
        client, _ = make_member_client()
        response = client.get(media_url(PROFILE_FILE))
        _assert_accel_redirect(response, PROFILE_FILE, "image/png")

    @pytest.mark.parametrize("relative_path", [GALLERY_FILE, PROFILE_FILE])
    def test_non_member_gets_403(self, write_media: WriteMedia, relative_path: str) -> None:
        write_media(relative_path)
        client = make_auth_client(make_user(username="visitor"))
        response = client.get(media_url(relative_path))
        assert response.status_code == 403
        assert response.data["error_code"] == "PERMISSION_DENIED"
        assert "X-Accel-Redirect" not in response

    def test_non_member_gets_own_profile_photo(self, write_media: WriteMedia) -> None:
        write_media(PROFILE_FILE)
        client = make_auth_client(make_user(username="ana.paula"))
        response = client.get(media_url(PROFILE_FILE))
        _assert_accel_redirect(response, PROFILE_FILE, "image/png")

    def test_non_member_with_legacy_username_gets_own_photo(self, write_media: WriteMedia) -> None:
        # Legacy usernames store the photo under the user id (profile_photo_path).
        owner = make_user(username="Ana Paula")
        own_photo = f"profiles/{owner.pk}/6f1c2d0e9a8b.png"
        write_media(own_photo)
        response = make_auth_client(owner).get(media_url(own_photo))
        _assert_accel_redirect(response, own_photo, "image/png")

    def test_missing_file_gets_404(self, media_root: Path) -> None:
        client, _ = make_member_client()
        response = client.get(media_url("gallery/retiro-2025/missing.jpg"))
        assert response.status_code == 404
        assert response.data["error_code"] == "NOT_FOUND"

    def test_head_gets_the_same_redirect(self, write_media: WriteMedia) -> None:
        write_media(GALLERY_FILE)
        client, _ = make_member_client()
        response = client.head(media_url(GALLERY_FILE))
        assert response.status_code == 200
        assert response["X-Accel-Redirect"] == f"/ipbcb/protected-media/{GALLERY_FILE}"

    def test_query_string_is_not_forwarded(self, write_media: WriteMedia) -> None:
        write_media(GALLERY_FILE)
        client, _ = make_member_client()
        response = client.get(media_url(GALLERY_FILE) + "?v=2")
        assert response["X-Accel-Redirect"] == f"/ipbcb/protected-media/{GALLERY_FILE}"


# ---------------------------------------------------------------------------
# US5 — the redirect header is ASCII-safe for Unicode filenames
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_unicode_filename_is_percent_encoded_in_redirect(write_media: WriteMedia) -> None:
    write_media("gallery/ceia-de-natal/Ceia_ção.jpg")
    client, _ = make_member_client()
    response = client.get(media_url("gallery/ceia-de-natal/Ceia_ção.jpg"))
    assert response.status_code == 200
    assert (
        response["X-Accel-Redirect"]
        == "/ipbcb/protected-media/gallery/ceia-de-natal/Ceia_%C3%A7%C3%A3o.jpg"
    )


# ---------------------------------------------------------------------------
# US3 — leader-only photos reserved before they exist
# ---------------------------------------------------------------------------

MEMBERS_FILE = "members/ana/photo.jpg"


@pytest.mark.django_db
class TestLeaderFolder:
    def test_plain_member_gets_403(self, write_media: WriteMedia) -> None:
        write_media(MEMBERS_FILE)
        client, _ = make_member_client()
        assert client.get(media_url(MEMBERS_FILE)).status_code == 403

    def test_plain_member_cannot_learn_that_a_file_is_missing(self, media_root: Path) -> None:
        client, _ = make_member_client()
        assert client.get(media_url("members/ana/nope.jpg")).status_code == 403

    def test_leader_who_is_not_a_member_gets_redirect(self, write_media: WriteMedia) -> None:
        write_media(MEMBERS_FILE)
        client, _ = make_admin_client()
        response = client.get(media_url(MEMBERS_FILE))
        assert response.status_code == 200
        assert response["X-Accel-Redirect"] == f"/ipbcb/protected-media/{MEMBERS_FILE}"


# ---------------------------------------------------------------------------
# US4 — files outside any known folder are not served to anyone
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDefaultDeny:
    @pytest.mark.parametrize(
        "relative_path", ["reports/2026.pdf", "logo.png", "gallery-old/x.jpg", "Gallery/x.jpg"]
    )
    def test_unruled_path_is_404_even_for_leader_and_member(
        self, write_media: WriteMedia, relative_path: str
    ) -> None:
        write_media(relative_path)
        client, user = make_admin_client()
        user.profile.is_member = True
        user.profile.save()
        response = client.get(media_url(relative_path))
        assert response.status_code == 404
        assert "X-Accel-Redirect" not in response


# ---------------------------------------------------------------------------
# US6 — local development enforces the same rules
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDevelopmentMode:
    @pytest.fixture(autouse=True)
    def _debug_on(self, media_root: Path, settings: SettingsWrapper) -> None:
        settings.DEBUG = True

    def test_member_gets_file_bytes(self, write_media: WriteMedia) -> None:
        write_media(GALLERY_FILE)
        client, _ = make_member_client()
        response = client.get(media_url(GALLERY_FILE))
        assert response.status_code == 200
        assert isinstance(response, FileResponse)
        assert b"".join(response.streaming_content) == GALLERY_BYTES
        assert response["Content-Type"] == "image/jpeg"
        assert response["Cache-Control"] == "private, no-cache"
        assert "X-Accel-Redirect" not in response

    def test_anonymous_gets_401(self, write_media: WriteMedia) -> None:
        write_media(GALLERY_FILE)
        assert APIClient().get(media_url(GALLERY_FILE)).status_code == 401

    def test_non_member_gets_403(self, write_media: WriteMedia) -> None:
        write_media(GALLERY_FILE)
        client = make_auth_client(make_user(username="visitor"))
        assert client.get(media_url(GALLERY_FILE)).status_code == 403
