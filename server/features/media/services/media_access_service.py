import logging
from typing import BinaryIO

from core.domain.exceptions import (
    MediaAccessDeniedError,
    MediaFileNotFoundError,
    MediaFileTrashedError,
    MediaFolderNotRuledError,
    MediaPathRejectedError,
)
from features.media.domain.media_rules import (
    FOLDER_RULES,
    MediaAccessOutcome,
    MediaAudience,
    audience_for_folder,
    content_type_for,
    first_segment,
    is_own_profile_file,
    validate_media_path,
)
from features.media.dtos.media_dtos import MediaFile, MediaViewer
from features.media.repositories.interfaces import MediaFileRepository, TrashedMediaLookup

logger = logging.getLogger(__name__)

GALLERY_FOLDER = "gallery"

_MediaDecisionError = (
    MediaPathRejectedError,
    MediaFolderNotRuledError,
    MediaAccessDeniedError,
    MediaFileNotFoundError,
)

_OUTCOME_BY_ERROR: dict[type[Exception], MediaAccessOutcome] = {
    MediaPathRejectedError: MediaAccessOutcome.REJECTED,
    MediaFolderNotRuledError: MediaAccessOutcome.UNRULED,
    MediaAccessDeniedError: MediaAccessOutcome.FORBIDDEN,
    MediaFileNotFoundError: MediaAccessOutcome.NOT_FOUND,
    MediaFileTrashedError: MediaAccessOutcome.TRASHED,
}


class MediaAccessService:
    """Decides whether a caller may read a file under MEDIA_ROOT.

    Order is the spec's: validate the path, pick the folder rule, check the caller, and only
    then look for the file — so a caller outside the folder's audience cannot learn whether a
    file exists there. Design in ``specs/009-protected-media-access/``. Under ``gallery/``, a
    file whose photo or album is in the trash is refused to members before the existence check
    (``specs/014-gallery-trash-sync/``).
    """

    def __init__(self, repository: MediaFileRepository, trashed_lookup: TrashedMediaLookup) -> None:
        self._repository = repository
        self._trashed = trashed_lookup

    def authorize(self, requested_path: str, viewer: MediaViewer) -> MediaFile:
        """Return the file to serve, or raise a media domain exception. Logs one decision.

        >>> service.authorize("gallery/retiro/x.jpg", member_viewer).relative_path
        'gallery/retiro/x.jpg'
        """
        try:
            media_file = self._decide(requested_path, viewer)
        except _MediaDecisionError as exc:
            self._log_decision(requested_path, _OUTCOME_BY_ERROR[type(exc)])
            raise
        self._log_decision(requested_path, MediaAccessOutcome.ALLOWED)
        return media_file

    def open(self, media_file: MediaFile) -> BinaryIO:
        """Open an authorized file for streaming by Django (development only).

        >>> service.open(service.authorize("gallery/retiro/x.jpg", member_viewer)).read()
        """
        return self._repository.open(media_file.absolute_path)

    def _decide(self, requested_path: str, viewer: MediaViewer) -> MediaFile:
        path = validate_media_path(requested_path)
        folder = first_segment(path)
        audience = audience_for_folder(folder)
        if audience is None:
            raise MediaFolderNotRuledError(path)
        if folder == GALLERY_FOLDER:
            self._check_gallery_file(path, viewer)
        elif not _viewer_may_read(path, viewer, audience):
            raise MediaAccessDeniedError(folder)
        return self._located_file(path)

    def _check_gallery_file(self, path: str, viewer: MediaViewer) -> None:
        """Membership, plus the trash rule of spec 014: a trashed item's file is ``404`` to a
        member and readable with ``owner``. Callers who are both, or neither, need no lookup."""
        if viewer.is_member and viewer.can_own_gallery:
            return
        if not (viewer.is_member or viewer.can_own_gallery):
            raise MediaAccessDeniedError(GALLERY_FOLDER)
        trashed = self._trashed.is_trashed(path)
        if trashed and not viewer.can_own_gallery:
            raise MediaFileTrashedError(path)
        if not trashed and not viewer.is_member:
            raise MediaAccessDeniedError(GALLERY_FOLDER)

    def _located_file(self, path: str) -> MediaFile:
        absolute_path = self._repository.locate(path)
        if absolute_path is None:
            raise MediaFileNotFoundError(path)
        return MediaFile(
            relative_path=path, absolute_path=absolute_path, content_type=content_type_for(path)
        )

    def _log_decision(self, requested_path: str, outcome: MediaAccessOutcome) -> None:
        # Folder and outcome only. The rest of the path can carry a username, and the first
        # segment of a rejected or unruled path is attacker-chosen text — neither is logged.
        folder = first_segment(requested_path)
        is_trusted_folder = outcome is not MediaAccessOutcome.REJECTED and folder in FOLDER_RULES
        logged_folder = folder if is_trusted_folder else None
        logger.info("media_access", extra={"folder": logged_folder, "outcome": outcome.value})


def _viewer_may_read(path: str, viewer: MediaViewer, audience: MediaAudience) -> bool:
    # Owner exception (spec FR-005a): a logged-in non-member still sees their own photo.
    if is_own_profile_file(path, viewer.own_profile_folder):
        return True
    return _viewer_in_audience(viewer, audience)


def _viewer_in_audience(viewer: MediaViewer, audience: MediaAudience) -> bool:
    if audience is MediaAudience.MEMBERS_SCOPE:
        return viewer.can_view_members
    return viewer.is_member
