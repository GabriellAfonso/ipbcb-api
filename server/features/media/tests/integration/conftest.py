from collections.abc import Callable
from pathlib import Path

import pytest
from pytest_django.fixtures import SettingsWrapper

GALLERY_FILE = "gallery/retiro-2025/IMG_0042.jpg"
GALLERY_BYTES = b"\xff\xd8gallery-bytes"


def media_url(relative_path: str) -> str:
    """URL the app requests. Test settings have no FORCE_SCRIPT_NAME, so the /ipbcb prefix
    is part of the route, exactly as the serializers emit it."""
    return f"/ipbcb/media/{relative_path}"


@pytest.fixture
def media_root(tmp_path: Path, settings: SettingsWrapper) -> Path:
    """An empty MEDIA_ROOT under tmp_path, with production delivery (X-Accel-Redirect).

    ``config/settings/test.py`` sets DEBUG=True; the view reads it per request, so tests of the
    development mode flip it back themselves.
    """
    root = tmp_path / "media"
    root.mkdir()
    settings.MEDIA_ROOT = root
    settings.DEBUG = False
    return root


@pytest.fixture
def write_media(media_root: Path) -> Callable[[str, bytes], Path]:
    def _write(relative_path: str, content: bytes = GALLERY_BYTES) -> Path:
        target = media_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return target

    return _write
