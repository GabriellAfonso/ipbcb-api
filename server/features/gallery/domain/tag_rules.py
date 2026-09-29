"""Pure rules of member tags: normalising a write and diffing it against the current tags.

No I/O. Every refusal here happens before the database is read, so a malformed bulk request
costs nothing (specs/015-gallery-member-tags research R-04).
"""

from collections.abc import Iterable, Mapping, Set
from dataclasses import dataclass, field

from core.domain.exceptions import TagBulkLimitError, TagListOverlapError, ValidationError

# One constant (spec FR-017): covers any real event (the largest album holds ~40 photos) while
# keeping one transaction and one response bounded.
TAG_BULK_PHOTO_LIMIT = 200


@dataclass(frozen=True)
class BulkTagRequest:
    """A bulk tag change after normalisation: no repeats, not empty, no member in both lists."""

    photo_ids: list[int]
    add_member_ids: list[int]
    remove_member_ids: list[int]


@dataclass(frozen=True)
class TagDiff:
    """Tags a write really changes, photo id -> member ids. Photos with nothing to change are
    absent, so only the photos listed here get a new ``updated_at`` and a log entry."""

    added: dict[int, list[int]] = field(default_factory=dict)
    removed: dict[int, list[int]] = field(default_factory=dict)

    @property
    def changed_photo_ids(self) -> list[int]:
        """>>> TagDiff(added={3: [12]}, removed={1: [40]}).changed_photo_ids
        [1, 3]
        """
        return sorted(set(self.added) | set(self.removed))

    @property
    def is_empty(self) -> bool:
        return not self.added and not self.removed


def dedupe(ids: Iterable[int]) -> list[int]:
    """Drop repeated ids, keeping the first appearance (spec FR-016).

    >>> dedupe([3, 1, 3, 2, 1])
    [3, 1, 2]
    """
    return list(dict.fromkeys(ids))


def normalise_bulk(
    photo_ids: Iterable[int], add_member_ids: Iterable[int], remove_member_ids: Iterable[int]
) -> BulkTagRequest:
    """Dedupe a bulk request and refuse it when empty, contradictory or too large, in that order.

    >>> normalise_bulk([1, 1], add_member_ids=[12], remove_member_ids=[]).photo_ids
    [1]
    """
    request = BulkTagRequest(dedupe(photo_ids), dedupe(add_member_ids), dedupe(remove_member_ids))
    _require_not_empty(request)
    _require_no_overlap(request)
    if len(request.photo_ids) > TAG_BULK_PHOTO_LIMIT:
        raise TagBulkLimitError(len(request.photo_ids), TAG_BULK_PHOTO_LIMIT)
    return request


def replace_diff(photo_id: int, current: Set[int], desired: Iterable[int]) -> TagDiff:
    """What turns ``current`` into exactly ``desired`` on one photo.

    >>> replace_diff(1, {12, 40}, [12, 7])
    TagDiff(added={1: [7]}, removed={1: [40]})
    """
    wanted = set(desired)
    return _diff_of({photo_id: sorted(wanted - current)}, {photo_id: sorted(current - wanted)})


def bulk_diff(
    current: Mapping[int, Set[int]], add: Iterable[int], remove: Iterable[int]
) -> TagDiff:
    """Pairs of ``add`` not tagged yet and pairs of ``remove`` that are, per photo in
    ``current`` (every photo of the request, untagged ones mapped to an empty set).

    >>> bulk_diff({1: {40}, 2: set()}, add=[12], remove=[40])
    TagDiff(added={1: [12], 2: [12]}, removed={1: [40]})
    """
    to_add, to_remove = set(add), set(remove)
    added = {photo: sorted(to_add - tags) for photo, tags in current.items()}
    removed = {photo: sorted(to_remove & tags) for photo, tags in current.items()}
    return _diff_of(added, removed)


def _diff_of(added: Mapping[int, list[int]], removed: Mapping[int, list[int]]) -> TagDiff:
    return TagDiff(
        added={photo: ids for photo, ids in added.items() if ids},
        removed={photo: ids for photo, ids in removed.items() if ids},
    )


def _require_not_empty(request: BulkTagRequest) -> None:
    if not request.photo_ids:
        raise ValidationError("Envie ao menos uma foto em 'photo_ids'.")
    if not request.add_member_ids and not request.remove_member_ids:
        raise ValidationError(
            "Envie ao menos um membro em 'add_member_ids' ou em 'remove_member_ids'."
        )


def _require_no_overlap(request: BulkTagRequest) -> None:
    overlap = set(request.add_member_ids) & set(request.remove_member_ids)
    if overlap:
        raise TagListOverlapError(sorted(overlap))
