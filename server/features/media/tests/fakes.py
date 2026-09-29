from io import BytesIO
from pathlib import Path
from typing import BinaryIO

FAKE_MEDIA_ROOT = Path("/fake-media")


class FakeMediaFileRepository:
    """In-memory media files keyed by relative path. Records every ``locate`` call so tests
    can assert the service never looked a file up before deciding permission."""

    def __init__(self, files: dict[str, bytes] | None = None) -> None:
        self._files = files or {}
        self.located: list[str] = []

    def locate(self, relative_path: str) -> Path | None:
        self.located.append(relative_path)
        if relative_path not in self._files:
            return None
        return FAKE_MEDIA_ROOT / relative_path

    def open(self, path: Path) -> BinaryIO:
        relative_path = path.relative_to(FAKE_MEDIA_ROOT).as_posix()
        return BytesIO(self._files[relative_path])


class FakeTrashedMediaLookup:
    """Paths of trashed gallery items, and every path asked about, so tests can assert when the
    service did or did not look (specs/014-gallery-trash-sync research R-05)."""

    def __init__(self, trashed: set[str] | None = None) -> None:
        self.trashed = trashed or set()
        self.asked: list[str] = []

    def is_trashed(self, relative_path: str) -> bool:
        self.asked.append(relative_path)
        return relative_path in self.trashed
