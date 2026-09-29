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


class TrashedMediaLookup(Protocol):
    """Whether a stored file belongs to a trashed gallery item. Declared here, implemented by
    the gallery and wired in ``config/di.py``, so neither feature imports the other
    (specs/014-gallery-trash-sync research R-05)."""

    def is_trashed(self, relative_path: str) -> bool:
        """True when ``relative_path`` is the original, thumbnail or cover of a trashed row."""
        ...
