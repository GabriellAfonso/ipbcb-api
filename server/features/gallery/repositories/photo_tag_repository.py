from collections.abc import Collection
from datetime import datetime
from uuid import UUID

from django.db.models import Count, Q

from core.time.clock import Clock
from features.gallery.domain.tag_rules import TagDiff
from features.gallery.dtos.tag_dtos import TaggedMember
from features.gallery.models.gallery import Photo
from features.gallery.models.tags import PhotoTag


class PhotoTagRepositoryImpl:
    """Member tags through the Django ORM (specs/015-gallery-member-tags).

    Member names come through ``PhotoTag.member``; the roll itself is never queried here. Every
    photo whose tags change gets ``updated_at`` from the injected clock, so the change feed sees
    it (research R-07).
    """

    def __init__(self, clock: Clock) -> None:
        self._clock = clock

    def lock_live_photos(self, photo_ids: Collection[int]) -> list[int]:
        """Lock the live photo rows among ``photo_ids``, by id so two writes over overlapping
        photos cannot deadlock; return the ids found. A trashed or unknown id is not returned.

        >>> repository.lock_live_photos([302, 301, 999])
        [301, 302]
        """
        locked = Photo.objects.select_for_update().filter(pk__in=photo_ids).order_by("id")
        return list(locked.values_list("id", flat=True))

    def current_tags(self, photo_ids: Collection[int]) -> dict[int, set[int]]:
        """Member ids tagged in each photo, every requested photo present (untagged: empty).

        >>> repository.current_tags([301, 302])
        {301: {12, 40}, 302: set()}
        """
        tags: dict[int, set[int]] = {photo_id: set() for photo_id in photo_ids}
        pairs = PhotoTag.objects.filter(photo_id__in=photo_ids).values_list("photo_id", "member_id")
        for photo_id, member_id in pairs:
            tags[photo_id].add(member_id)
        return tags

    def write_diff(self, diff: TagDiff, actor_id: UUID | None) -> None:
        """Insert the added pairs, delete the removed ones and mark only the photos that changed.

        The diff was computed under the photo row locks, so no added pair exists yet; a member
        deleted meanwhile makes the insert fail on its foreign key, and the caller maps it.
        """
        if diff.is_empty:
            return
        now = self._clock.now()
        PhotoTag.objects.bulk_create(_new_tags(diff, actor_id, now))
        PhotoTag.objects.filter(_pairs(diff.removed)).delete()
        Photo.objects.filter(pk__in=diff.changed_photo_ids).update(updated_at=now)

    def tagged_members(self) -> list[TaggedMember]:
        """Members tagged in at least one live photo, with how many, by name then id.

        Starting from ``PhotoTag`` bypasses ``Photo``'s live-only manager, hence the explicit
        filter: without it a trashed photo would still count (research R-08).

        >>> repository.tagged_members()[0]
        TaggedMember(id=40, name='João Lima', photo_count=3)
        """
        rows = (
            PhotoTag.objects.filter(photo__deleted_at__isnull=True)
            .values("member_id", "member__name")
            .annotate(photo_count=Count("photo_id"))
            .order_by("member__name", "member_id")
        )
        return [
            TaggedMember(
                id=row["member_id"], name=row["member__name"], photo_count=row["photo_count"]
            )
            for row in rows
        ]

    def touch_photos_if_renamed(self, member_id: int, new_name: str) -> None:
        """Mark the member's live photos as changed when ``new_name`` differs from the stored
        name. Called before the save, so the row still holds the old name; a member tagged
        nowhere costs one ``EXISTS`` and nothing else.
        """
        renamed = (
            PhotoTag.objects.filter(member_id=member_id).exclude(member__name=new_name).exists()
        )
        if renamed:
            self.touch_photos_of_member(member_id)

    def touch_photos_of_member(self, member_id: int) -> None:
        """Mark every live photo the member is tagged in as changed. Trashed photos are left
        alone: their restore marks them anyway (spec 014 FR-020)."""
        photos = Photo.objects.filter(tags__member_id=member_id)
        photos.update(updated_at=self._clock.now())


def _new_tags(diff: TagDiff, actor_id: UUID | None, now: datetime) -> list[PhotoTag]:
    return [
        PhotoTag(photo_id=photo_id, member_id=member_id, tagged_by_id=actor_id, tagged_at=now)
        for photo_id, member_ids in diff.added.items()
        for member_id in member_ids
    ]


def _pairs(by_photo: dict[int, list[int]]) -> Q:
    """One ``OR`` of (photo, members) conditions; matches nothing when ``by_photo`` is empty."""
    condition = Q(pk__in=[])
    for photo_id, member_ids in by_photo.items():
        condition |= Q(photo_id=photo_id, member_id__in=member_ids)
    return condition
