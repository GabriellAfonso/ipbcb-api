from pathlib import Path

from core.application.dtos.strict_base import StrictBaseModel


class MediaViewer(StrictBaseModel):
    """What the media access service knows about the caller.

    Built by the view from the project's permission classes, so the service never sees the
    HTTP request. ``own_profile_folder`` is the caller's folder under ``profiles/``, so the
    owner can read their own photo without being a member.

    >>> MediaViewer(is_member=True, can_view_members=False, own_profile_folder="ana.paula")
    """

    is_member: bool
    can_view_members: bool
    own_profile_folder: str | None = None


class MediaFile(StrictBaseModel):
    """A media file the caller may read.

    ``relative_path`` is the validated requested path, verbatim — the same string that was
    checked is the one sent to nginx. ``absolute_path`` is only used when Django streams the
    file itself (development).

    >>> MediaFile(relative_path="gallery/a/x.jpg", absolute_path=Path("/m/gallery/a/x.jpg"),
    ...           content_type="image/jpeg")
    """

    relative_path: str
    absolute_path: Path
    content_type: str
