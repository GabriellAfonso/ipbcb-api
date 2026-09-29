"""Named fakes for member tags (specs/015-gallery-member-tags)."""

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from uuid import UUID

from django.db import IntegrityError

from features.gallery.domain.tag_rules import TagDiff
from features.gallery.dtos.tag_dtos import MemberRef, TaggedMember
from features.gallery.tests.fakes import FakeGalleryRepository


@dataclass(frozen=True)
class FakeMember:
    """Stands in for the members feature's DTO: structurally a ``NamedMember``."""

    id: int
    name: str


class FakeMemberDirectory:
    """The roll as a dict id -> name. ``vanish_on_write`` removes a member between the existence
    check and the insert, as a concurrent deletion would."""

    def __init__(self, names: dict[int, str] | None = None) -> None:
        self.names: dict[int, str] = dict(names or {})

    def list_names(self) -> Sequence[FakeMember]:
        ordered = sorted(self.names.items(), key=lambda item: (item[1], item[0]))
        return [FakeMember(id=member_id, name=name) for member_id, name in ordered]

    def existing_ids(self, member_ids: Collection[int]) -> set[int]:
        return {member_id for member_id in member_ids if member_id in self.names}


class FakePhotoTagRepository:
    """Tags kept per photo of a ``FakeGalleryRepository``, which it updates so photo views carry
    ``members`` and a new ``updated_at``, as the real prefetch and bump would.

    ``vanish_member_on_write`` deletes that member from the directory and makes ``write_diff``
    raise ``IntegrityError`` when it would insert them — the foreign-key race of research R-04.
    """

    def __init__(self, photos: FakeGalleryRepository, directory: FakeMemberDirectory) -> None:
        self.photos = photos
        self.directory = directory
        self.tags: dict[int, set[int]] = {}
        self.writes: list[TagDiff] = []
        self.actors: list[UUID | None] = []
        self.touched_members: list[int] = []
        self.vanish_member_on_write: int | None = None

    def tag(self, photo_id: int, *member_ids: int) -> None:
        """Test helper: tags set directly, bypassing the service."""
        self.tags.setdefault(photo_id, set()).update(member_ids)
        self._refresh(photo_id)

    def lock_live_photos(self, photo_ids: Collection[int]) -> list[int]:
        return sorted(photo_id for photo_id in set(photo_ids) if photo_id in self.photos.photos)

    def current_tags(self, photo_ids: Collection[int]) -> dict[int, set[int]]:
        return {photo_id: set(self.tags.get(photo_id, set())) for photo_id in photo_ids}

    def write_diff(self, diff: TagDiff, actor_id: UUID | None) -> None:
        self._raise_if_member_vanished(diff)
        self.writes.append(diff)
        self.actors.append(actor_id)
        for photo_id, member_ids in diff.added.items():
            self.tags.setdefault(photo_id, set()).update(member_ids)
        for photo_id, member_ids in diff.removed.items():
            self.tags.get(photo_id, set()).difference_update(member_ids)
        for photo_id in diff.changed_photo_ids:
            self._refresh(photo_id)

    def tagged_members(self) -> list[TaggedMember]:
        counts: dict[int, int] = {}
        for photo_id, member_ids in self.tags.items():
            if photo_id in self.photos.photos:
                for member_id in member_ids:
                    counts[member_id] = counts.get(member_id, 0) + 1
        rows = [
            TaggedMember(id=m, name=self.directory.names[m], photo_count=n)
            for m, n in counts.items()
        ]
        return sorted(rows, key=lambda row: (row.name, row.id))

    def touch_photos_if_renamed(self, member_id: int, new_name: str) -> None:
        if self.directory.names.get(member_id) != new_name:
            self.touch_photos_of_member(member_id)

    def touch_photos_of_member(self, member_id: int) -> None:
        self.touched_members.append(member_id)

    def _raise_if_member_vanished(self, diff: TagDiff) -> None:
        vanished = self.vanish_member_on_write
        if vanished is None or not any(vanished in ids for ids in diff.added.values()):
            return
        self.directory.names.pop(vanished, None)
        raise IntegrityError("FOREIGN KEY constraint failed")

    def _refresh(self, photo_id: int) -> None:
        members = [
            MemberRef(id=m, name=self.directory.names.get(m, f"#{m}"))
            for m in self.tags.get(photo_id, set())
        ]
        members.sort(key=lambda ref: (ref.name, ref.id))
        self.photos.update_photo(photo_id, {"members": members})
