"""DTOs of reading progress and its offline sync (specs/025-bible-videos)."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field

from core.application.dtos.strict_base import StrictBaseModel

# Fits a whole book (Salmos = 150) with margin.
MAX_SYNC_CHANGES = 500

# Rejection reasons. Stable API surface: the app logs and switches on them.
REASON_UNKNOWN_BOOK = "unknown_book"
REASON_UNKNOWN_CHAPTER = "unknown_chapter"
REASON_UNKNOWN_VIDEO = "unknown_video"
REASON_WITHOUT_OFFSET = "changed_at_without_offset"
REASON_IN_FUTURE = "changed_at_in_future"


class ChapterChangeDTO(StrictBaseModel):
    """Marking or unmarking one chapter as read. Book and chapter are checked per item by the
    service, so a bad one rejects only this item."""

    type: Literal["chapter"]
    book: str = Field(min_length=1, max_length=8)
    chapter: int
    done: bool
    changed_at: datetime


class VideoChangeDTO(StrictBaseModel):
    type: Literal["video"]
    video_id: int
    done: bool
    changed_at: datetime


ProgressChangeDTO = Annotated[ChapterChangeDTO | VideoChangeDTO, Field(discriminator="type")]


class ProgressSyncDTO(StrictBaseModel):
    """``POST api/bible/progress/sync/``. Shape errors refuse the whole batch (FR-022).

    >>> ProgressSyncDTO.model_validate({"changes": [{"type": "video", "video_id": 4,
    ...     "done": True, "changed_at": "2026-10-27T10:00:00-03:00"}]})
    """

    changes: list[ProgressChangeDTO] = Field(min_length=1, max_length=MAX_SYNC_CHANGES)


class RejectedChangeDTO(StrictBaseModel):
    index: int
    reason: str


class ProgressSyncResultDTO(StrictBaseModel):
    """Every index of the batch, in exactly one of the two lists."""

    accepted: list[int]
    rejected: list[RejectedChangeDTO]


class ProgressStateDTO(StrictBaseModel):
    """Done items only: chapters by canonical book, video ids."""

    chapters: dict[str, list[int]]
    videos: list[int]


class ChapterMarkDTO(StrictBaseModel):
    """A stored or to-be-stored chapter row; ``book`` canonical, ``changed_at`` aware."""

    book: str
    chapter: int
    done: bool
    changed_at: datetime


class VideoMarkDTO(StrictBaseModel):
    video_id: int
    done: bool
    changed_at: datetime
