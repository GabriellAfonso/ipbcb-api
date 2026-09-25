from collections.abc import Callable
from pathlib import Path

import pytest

from conftest import make_member_client
from features.media.tests.integration.conftest import media_url

SENTINEL_BYTES = b"sentinel-outside-media-root"


@pytest.fixture
def sentinel(media_root: Path) -> Path:
    """A file right next to MEDIA_ROOT, one ``..`` away from escaping it."""
    target = media_root.parent / "sentinel.txt"
    target.write_bytes(SENTINEL_BYTES)
    return target


@pytest.mark.django_db
class TestTraversalIsRejected:
    """The Django test client percent-decodes the path once, like the ASGI server does, so
    "%2e%2e" arrives as ".." and "%252e" arrives as "%2e"."""

    @pytest.mark.parametrize(
        "requested",
        [
            "gallery/../../sentinel.txt",
            "gallery/%2e%2e/%2e%2e/sentinel.txt",
            "gallery/..%2f..%2fsentinel.txt",
            "gallery/%252e%252e/%252e%252e/sentinel.txt",
            "/etc/passwd",
            "gallery/../gallery/x.jpg",
            r"gallery\..\..\sentinel.txt",
        ],
    )
    def test_rejected_with_404_and_no_redirect(
        self, sentinel: Path, write_media: Callable[..., Path], requested: str
    ) -> None:
        write_media("gallery/x.jpg")
        client, _ = make_member_client()
        response = client.get(media_url(requested))
        assert response.status_code == 404
        assert "X-Accel-Redirect" not in response
        assert SENTINEL_BYTES not in response.content
