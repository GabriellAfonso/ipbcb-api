from datetime import date, datetime
from uuid import UUID

from core.application.dtos.strict_base import StrictBaseModel


class AlbumRecord(StrictBaseModel):
    """An album row as the repository reads it; ``cover_name`` is empty without a cover."""

    id: int
    name: str
    parent_id: int | None
    description: str
    event_date: date | None
    position: int
    cover_name: str


class AlbumView(StrictBaseModel):
    """An album as members read it; ``cover_path`` is the resolved cover's URL path."""

    id: int
    name: str
    parent_id: int | None
    description: str
    event_date: date | None
    cover_path: str | None
    cover_source_album_id: int | None


class AlbumCreate(StrictBaseModel):
    name: str
    parent_id: int | None = None
    description: str = ""
    event_date: date | None = None


class AlbumChanges(StrictBaseModel):
    """Partial album update. Which fields were sent is ``model_fields_set``: an absent
    ``parent_id`` means "do not move", an explicit ``None`` means "move to the root"."""

    name: str | None = None
    parent_id: int | None = None
    description: str | None = None
    event_date: date | None = None


class SiblingOrder(StrictBaseModel):
    """Full new order of the children of ``parent_id`` (the roots when ``None``)."""

    parent_id: int | None
    ids: list[int]


class PhotoView(StrictBaseModel):
    """A photo as members read it; ``*_path`` fields are URL paths, made absolute by the view."""

    id: int
    name: str
    description: str
    album_id: int
    album_name: str
    image_path: str | None
    thumbnail_path: str | None
    date_taken: date | None
    uploaded_at: datetime


class NewPhoto(StrictBaseModel):
    """A photo whose files are already stored, ready for its row."""

    album_id: int
    image_name: str
    thumbnail_name: str
    name: str
    date_taken: date | None
    uploader_id: UUID | None


class PhotoChanges(StrictBaseModel):
    """Partial photo update; ``model_fields_set`` says which fields were sent."""

    name: str | None = None
    description: str | None = None
    date_taken: date | None = None
    album_id: int | None = None


class RejectedFile(StrictBaseModel):
    filename: str
    reason: str


class UploadResult(StrictBaseModel):
    """Result of a batch photo upload: stored photos, and each refused file with its reason."""

    accepted: list[PhotoView] = []
    rejected: list[RejectedFile] = []

    @property
    def has_errors(self) -> bool:
        return len(self.rejected) > 0


class ThumbnailBackfillReport(StrictBaseModel):
    filled: int
    skipped_ids: list[int]
