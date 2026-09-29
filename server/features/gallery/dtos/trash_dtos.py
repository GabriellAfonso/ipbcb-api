from datetime import date, datetime
from uuid import UUID

from core.application.dtos.strict_base import StrictBaseModel
from features.gallery.domain.trash_rules import TrashedItemKind


class TrashedRoot(StrictBaseModel):
    """The item a deletion batch is rooted at, as restore needs it. ``parent_album_id`` is the
    album's parent, or the photo's album (``None`` for a root album)."""

    batch_id: UUID
    kind: TrashedItemKind
    root_id: int
    name: str
    parent_album_id: int | None


class TrashEntryRow(StrictBaseModel):
    """One deletion batch as the repository reads it for the trash listing."""

    kind: TrashedItemKind
    id: int
    name: str
    deleted_at: datetime
    deleted_by: str | None
    uploaded_by: str | None
    sub_album_count: int
    photo_count: int
    thumbnail_name: str | None


class TrashEntry(StrictBaseModel):
    """A trash entry as owners read it; ``thumbnail_path`` is a URL path."""

    kind: TrashedItemKind
    id: int
    name: str
    deleted_at: datetime
    deleted_by: str | None
    uploaded_by: str | None
    purge_on: date
    sub_album_count: int
    photo_count: int
    thumbnail_path: str | None


class TrashOutcome(StrictBaseModel):
    """What one delete or restore touched: the batch and every row in it, for marks and logs."""

    batch_id: UUID
    kind: TrashedItemKind
    root_id: int
    album_ids: list[int]
    photo_ids: list[int]


class PurgedBatch(StrictBaseModel):
    """Rows deleted for good by one batch purge, and the files to remove once it commits."""

    album_ids: list[int]
    photo_ids: list[int]
    file_names: list[str]


class PurgeReport(StrictBaseModel):
    batches: int
    albums: int
    photos: int
    skipped_batch_ids: list[UUID]
    marks_expired: int
