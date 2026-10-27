"""The two kinds of gallery item. A video is a ``Photo`` row whose ``media_type`` is ``video``
(specs/023-gallery-videos research R-01)."""

from typing import Final, Literal

MediaType = Literal["photo", "video"]

PHOTO: Final = "photo"
VIDEO: Final = "video"
MEDIA_TYPES: Final[tuple[MediaType, ...]] = (PHOTO, VIDEO)
