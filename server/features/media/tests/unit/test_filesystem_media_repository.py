import os
from pathlib import Path

import pytest

from features.media.repositories.filesystem_media_repository import FileSystemMediaRepository


def _write(root: Path, relative_path: str, content: bytes = b"img") -> Path:
    target = root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target


class TestLocate:
    def test_existing_file_returns_resolved_path(self, tmp_path: Path) -> None:
        written = _write(tmp_path, "gallery/a/x.jpg")
        repository = FileSystemMediaRepository(root=tmp_path)
        assert repository.locate("gallery/a/x.jpg") == written.resolve()

    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        repository = FileSystemMediaRepository(root=tmp_path)
        assert repository.locate("gallery/a/missing.jpg") is None

    def test_directory_returns_none(self, tmp_path: Path) -> None:
        _write(tmp_path, "gallery/a/x.jpg")
        repository = FileSystemMediaRepository(root=tmp_path)
        assert repository.locate("gallery/a") is None


class TestOpen:
    def test_returns_file_bytes(self, tmp_path: Path) -> None:
        written = _write(tmp_path, "gallery/a/x.jpg", b"\xff\xd8bytes")
        repository = FileSystemMediaRepository(root=tmp_path)
        with repository.open(written) as handle:
            assert handle.read() == b"\xff\xd8bytes"


class TestSymlinkContainment:
    def test_symlink_escaping_the_root_is_not_located(self, tmp_path: Path) -> None:
        outside = _write(tmp_path, "outside/secret.jpg", b"secret")
        root = tmp_path / "media"
        link = root / "gallery/a/link.jpg"
        link.parent.mkdir(parents=True)
        try:
            os.symlink(outside, link)
        except OSError:
            pytest.skip("OS refuses to create symlinks (Windows without developer mode)")
        assert FileSystemMediaRepository(root=root).locate("gallery/a/link.jpg") is None
