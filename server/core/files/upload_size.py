"""Size of an uploaded file, shared by the image and video validators and the gallery's stored
``file_size`` (specs/023-gallery-videos research R-03)."""

import os
from typing import IO


def upload_size(upload: IO[bytes]) -> int | None:
    """Size in bytes, from Django's ``size`` when present or by measuring the stream; ``None``
    when the stream cannot be measured. The read position is left where it was.

    >>> upload_size(request.FILES["video"])
    41943040
    """
    size = getattr(upload, "size", None)
    if size is not None:
        return int(size)
    try:
        current = upload.tell()
        upload.seek(0, os.SEEK_END)
        measured = upload.tell()
        upload.seek(current)
        return measured
    except (OSError, ValueError):
        return None
