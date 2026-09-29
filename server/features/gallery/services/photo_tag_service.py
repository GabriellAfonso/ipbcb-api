import logging
from collections.abc import Collection, Iterator
from contextlib import contextmanager
from uuid import UUID

from django.db import IntegrityError, transaction

from core.domain.exceptions import PhotoNotFoundError, PhotoTagReferenceError
from features.gallery.domain.tag_rules import (
    TagDiff,
    bulk_diff,
    dedupe,
    normalise_bulk,
    replace_diff,
)
from features.gallery.dtos.gallery_dtos import PhotoView
from features.gallery.dtos.tag_dtos import (
    MemberRef,
    PhotoMembersReplace,
    PhotoTagsBulkChange,
    TaggedMember,
)
from features.gallery.repositories.interfaces import (
    GalleryRepository,
    MemberDirectory,
    PhotoTagRepository,
)

logger = logging.getLogger("features.gallery")


class PhotoTagService:
    """Member tags: the two writes, the picker and the tagged-member list
    (specs/015-gallery-member-tags).

    Each write runs in one transaction under a lock of the live photo rows, so concurrent writes
    on one photo apply whole, one after the other; any missing photo or member refuses the whole
    request with every offending id at once (research R-04).
    """

    def __init__(
        self,
        tag_repository: PhotoTagRepository,
        member_directory: MemberDirectory,
        gallery_repository: GalleryRepository,
    ) -> None:
        self._tags = tag_repository
        self._members = member_directory
        self._photos = gallery_repository

    def replace_photo_members(
        self, photo_id: int, change: PhotoMembersReplace, actor_id: UUID | None
    ) -> PhotoView:
        """Tag exactly ``change.member_ids`` in the photo; ``[]`` clears its tags.

        >>> service.replace_photo_members(301, PhotoMembersReplace(member_ids=[12]), user_id).members
        [MemberRef(id=12, name='Maria Souza')]
        """
        member_ids = dedupe(change.member_ids)
        with self._mapping_member_races(member_ids):
            with transaction.atomic():
                if not self._tags.lock_live_photos([photo_id]):
                    raise PhotoNotFoundError(photo_id)
                self._require_members(member_ids)
                current = self._tags.current_tags([photo_id])[photo_id]
                diff = replace_diff(photo_id, current, member_ids)
                self._tags.write_diff(diff, actor_id)
        _log_tag_change(diff, actor_id)
        return self._views([photo_id])[0]

    def change_tags(self, change: PhotoTagsBulkChange, actor_id: UUID | None) -> list[PhotoView]:
        """Add and remove the listed pairs on every listed photo; every other tag stays.

        >>> change = PhotoTagsBulkChange(photo_ids=[301, 302], add_member_ids=[12])
        >>> [photo.id for photo in service.change_tags(change, user_id)]
        [301, 302]
        """
        request = normalise_bulk(change.photo_ids, change.add_member_ids, change.remove_member_ids)
        member_ids = [*request.add_member_ids, *request.remove_member_ids]
        with self._mapping_member_races(member_ids):
            with transaction.atomic():
                self._require_references(request.photo_ids, member_ids)
                current = self._tags.current_tags(request.photo_ids)
                diff = bulk_diff(current, request.add_member_ids, request.remove_member_ids)
                self._tags.write_diff(diff, actor_id)
        _log_tag_change(diff, actor_id)
        return self._views(request.photo_ids)

    def taggable_members(self) -> list[MemberRef]:
        """Every member on the roll, active or not, as id and name, by name then id.

        >>> service.taggable_members()[0]
        MemberRef(id=40, name='João Lima')
        """
        return [MemberRef(id=member.id, name=member.name) for member in self._members.list_names()]

    def tagged_members(self) -> list[TaggedMember]:
        """Members tagged in at least one live photo, with how many, by name then id.

        >>> service.tagged_members()[0].photo_count
        3
        """
        return self._tags.tagged_members()

    def _require_references(self, photo_ids: list[int], member_ids: list[int]) -> None:
        missing_photos = set(photo_ids) - set(self._tags.lock_live_photos(photo_ids))
        missing_members = set(member_ids) - self._members.existing_ids(member_ids)
        if missing_photos or missing_members:
            raise PhotoTagReferenceError(sorted(missing_photos), sorted(missing_members))

    def _require_members(self, member_ids: list[int]) -> None:
        missing = set(member_ids) - self._members.existing_ids(member_ids)
        if missing:
            raise PhotoTagReferenceError([], sorted(missing))

    @contextmanager
    def _mapping_member_races(self, member_ids: Collection[int]) -> Iterator[None]:
        """A member deleted after the existence check fails the insert (or the commit, where
        foreign keys are deferred) on its foreign key: report it like any unknown member. The
        transaction has rolled back, so no tag points at nothing (spec Edge Cases)."""
        try:
            yield
        except IntegrityError:
            missing = set(member_ids) - self._members.existing_ids(member_ids)
            if not missing:
                raise
            raise PhotoTagReferenceError([], sorted(missing)) from None

    def _views(self, photo_ids: list[int]) -> list[PhotoView]:
        views = [self._photos.get_photo(photo_id) for photo_id in photo_ids]
        return [view for view in views if view is not None]


def _log_tag_change(diff: TagDiff, actor_id: UUID | None) -> None:
    # Ids only: a tag ties a named person to a photo (constitution; research R-11). A write that
    # changed nothing says nothing.
    if diff.is_empty:
        return
    logger.info(
        "gallery_tags_changed",
        extra={
            "photo_ids": diff.changed_photo_ids,
            "added": _keyed(diff.added),
            "removed": _keyed(diff.removed),
            "actor_id": str(actor_id) if actor_id else None,
        },
    )


def _keyed(by_photo: dict[int, list[int]]) -> dict[str, list[int]]:
    """JSON object keys are strings; say so here rather than let the formatter decide."""
    return {str(photo_id): member_ids for photo_id, member_ids in sorted(by_photo.items())}
