from datetime import date, datetime
from uuid import UUID

from core.application.dtos.strict_base import StrictBaseModel
from features.gallery.domain.media_types import PHOTO, MediaType
from features.gallery.dtos.tag_dtos import MemberRef


class AlbumRecord(StrictBaseModel):
    """An album row as the repository reads it; ``cover_name`` is empty without a cover."""

    id: int
    name: str
    parent_id: int | None
    description: str
    event_date: date | None
    position: int
    cover_name: str
    updated_at: datetime


class AlbumView(StrictBaseModel):
    """An album as members read it; ``cover_path`` is the resolved cover's URL path.
    ``updated_at`` feeds the change feed and is never serialized."""

    id: int
    name: str
    parent_id: int | None
    description: str
    event_date: date | None
    cover_path: str | None
    cover_source_album_id: int | None
    position: int
    updated_at: datetime


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
    """A photo as members read it; ``*_path`` fields are URL paths, made absolute by the view.
    ``updated_at`` feeds the change feed and is never serialized."""

    id: int
    name: str
    description: str
    album_id: int
    album_name: str
    image_path: str | None
    thumbnail_path: str | None
    date_taken: date | None
    uploaded_at: datetime
    position: int
    updated_at: datetime
    # The photo's tags, by name then id (specs/015-gallery-member-tags R-06).
    members: list[MemberRef] = []
    # specs/023-gallery-videos: for a video, ``image_path`` is the video file and
    # ``thumbnail_path`` its poster.
    media_type: MediaType = PHOTO
    duration_ms: int | None = None
    file_size: int | None = None


class NewPhoto(StrictBaseModel):
    """A photo whose files are already stored, ready for its row."""

    album_id: int
    image_name: str
    thumbnail_name: str
    name: str
    date_taken: date | None
    uploader_id: UUID | None
    client_upload_id: str | None = None
    media_type: MediaType = PHOTO
    duration_ms: int | None = None
    file_size: int | None = None


class VideoUploadMeta(StrictBaseModel):
    """What the uploader's phone sends with a video besides the two files: the server never
    reads the video's content (specs/023-gallery-videos FR-009, FR-014)."""

    duration_ms: int
    date_taken: date | None = None
    client_upload_id: str


class ClientUploadMatch(StrictBaseModel):
    """The row carrying a client upload id: which photo, and whether it is in the trash
    (specs/016-photo-upload-idempotency R-03)."""

    photo_id: int
    trashed: bool


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


class FileSizeBackfillReport(StrictBaseModel):
    """Result of ``fill_gallery_file_sizes``: items filled, and those whose file is missing."""

    filled: int
    skipped_ids: list[int]
