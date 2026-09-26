from functools import partial
from typing import IO
from uuid import UUID

from django.db import transaction

from core.domain.exceptions import MemberNotFoundError
from core.files.image_validation import detect_image_extension
from features.members.domain.member_changes import PHOTO_CHANGED, PHOTO_FIELD, PHOTO_REMOVED
from features.members.dtos import MemberFieldChange
from features.members.repositories.interfaces import (
    MemberChangeLogRepository,
    MemberPhotoStorage,
    MemberRosterRepository,
)
from features.members.services.member_write_log import log_member_write


class MemberPhotoService:
    """Leader-only member photo: upload, replace, remove.

    Storage cannot join a database transaction, so the order is chosen for every failure to
    leave the row pointing at a file that exists: the new file is written first, the row and
    the history entry commit together, and the old file is removed only after the commit
    (specs/010-members-management/research.md R-05).
    """

    def __init__(
        self,
        roster_repository: MemberRosterRepository,
        change_log_repository: MemberChangeLogRepository,
        photo_storage: MemberPhotoStorage,
    ) -> None:
        self._roster = roster_repository
        self._change_log = change_log_repository
        self._storage = photo_storage

    def replace_photo(
        self, member_id: int, upload: IO[bytes], editor_id: UUID | None
    ) -> str | None:
        """Store ``upload`` as the member's photo and return its URL path.

        Validated by decoded content before anything is touched, so a rejected file leaves
        the current photo intact.

        >>> service.replace_photo(12, open("ana.jpg", "rb"), leader_id)
        '/ipbcb/media/members/6f1c2d0e....jpg'
        """
        self._require_member(member_id)
        extension = detect_image_extension(upload)
        old_name = self._roster.get_photo_name(member_id)
        new_name = self._storage.save(extension, upload)
        try:
            self._commit_photo(member_id, new_name, old_name, editor_id, PHOTO_CHANGED)
        except Exception:
            self._storage.delete(new_name)
            raise
        log_member_write("member_photo_replaced", member_id, editor_id, changed_fields=1)
        record = self._roster.get_record(member_id)
        return record.photo_path if record else None

    def remove_photo(self, member_id: int, editor_id: UUID | None) -> None:
        """Remove the member's photo; without one, do nothing and write no history.

        >>> service.remove_photo(12, leader_id)
        """
        self._require_member(member_id)
        old_name = self._roster.get_photo_name(member_id)
        if old_name is None:
            return
        self._commit_photo(member_id, None, old_name, editor_id, PHOTO_REMOVED)
        log_member_write("member_photo_removed", member_id, editor_id, changed_fields=1)

    def _commit_photo(
        self,
        member_id: int,
        new_name: str | None,
        old_name: str | None,
        editor_id: UUID | None,
        marker: str,
    ) -> None:
        # The history carries the marker only: file paths never appear in it (FR-018).
        change = MemberFieldChange(field=PHOTO_FIELD, old_value=None, new_value=marker)
        with transaction.atomic():
            self._roster.set_photo_name(member_id, new_name)
            self._change_log.add_entries(member_id, editor_id, [change])
            if old_name:
                transaction.on_commit(partial(self._storage.delete, old_name), robust=True)

    def _require_member(self, member_id: int) -> None:
        if not self._roster.exists(member_id):
            raise MemberNotFoundError(member_id)
