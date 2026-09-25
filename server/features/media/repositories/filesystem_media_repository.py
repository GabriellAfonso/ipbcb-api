from pathlib import Path
from typing import BinaryIO

from features.media.repositories.interfaces import MediaFileRepository


class FileSystemMediaRepository(MediaFileRepository):
    """Media files on local disk under ``root`` (MEDIA_ROOT).

    >>> FileSystemMediaRepository(root=Path("/server/media")).locate("gallery/a/x.jpg")
    """

    def __init__(self, root: Path) -> None:
        self._root = root

    def locate(self, relative_path: str) -> Path | None:
        # Containment is judged on the resolved file, after symlinks: a link inside the root
        # pointing outside it must not be served. The service already rejected "..".
        try:
            root = self._root.resolve(strict=True)
            candidate = (root / relative_path).resolve(strict=True)
        except OSError:
            return None
        if not candidate.is_relative_to(root) or not candidate.is_file():
            return None
        return candidate

    def open(self, path: Path) -> BinaryIO:
        return path.open("rb")
