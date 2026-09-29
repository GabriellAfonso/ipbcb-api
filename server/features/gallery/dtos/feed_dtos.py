from core.application.dtos.strict_base import StrictBaseModel
from features.gallery.dtos.gallery_dtos import AlbumView, PhotoView


class ChangeFeed(StrictBaseModel):
    """What changed in the gallery since a cursor (specs/014-gallery-trash-sync contract)."""

    albums: list[AlbumView]
    photos: list[PhotoView]
    deleted_album_ids: list[int]
    deleted_photo_ids: list[int]
    cursor: str
    full_sync_required: bool
