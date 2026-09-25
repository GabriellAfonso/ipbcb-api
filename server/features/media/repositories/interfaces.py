from pathlib import Path
from typing import BinaryIO, Protocol


class MediaFileRepository(Protocol):
    """Filesystem access for media files, so the access service stays pure logic."""

    def locate(self, relative_path: str) -> Path | None:
        """Resolved path of a regular file inside the media root, or None — missing, not a
        regular file, or resolving (through symlinks) outside the root."""
        ...

    def open(self, path: Path) -> BinaryIO:
        """Open a located file for binary reading."""
        ...
