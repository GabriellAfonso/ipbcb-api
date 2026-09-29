from pathlib import Path

import pytest
from pytest_django.fixtures import SettingsWrapper


@pytest.fixture
def media_root(tmp_path: Path, settings: SettingsWrapper) -> Path:
    """An empty MEDIA_ROOT; ``default_storage`` follows the setting change."""
    root = tmp_path / "media"
    root.mkdir()
    settings.MEDIA_ROOT = root
    return root
