"""Pure rules of the gallery trash: retention windows, subtrees and purge order.

No I/O. Every tree walk keeps a visited set, like ``album_tree``, so a cycle that reached the
database by any path cannot hang a delete or a purge (specs/014-gallery-trash-sync research R-03,
R-09).
"""

from collections.abc import Collection, Mapping
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum


class TrashedItemKind(StrEnum):
    """What a deletion batch is rooted at, and what a deletion mark names. The value is stored
    and sent on the wire."""

    ALBUM = "album"
    PHOTO = "photo"


# How long a deleted album or photo stays restorable before the purge removes it.
TRASH_RETENTION = timedelta(days=30)

# How long the change feed keeps reporting a deleted id, whether or not its row was purged.
MARK_RETENTION = timedelta(days=90)

# Every write that sets `updated_at` runs in a request (gunicorn --timeout 60) or in a short
# per-row transaction, so none commits more than 60 s after taking its timestamp. Re-reading 90 s
# before each cursor means a late commit is never skipped (research R-07).
CURSOR_OVERLAP = timedelta(seconds=90)


def subtree_ids(root_id: int, parent_of: Mapping[int, int | None]) -> list[int]:
    """The album and every descendant found in ``parent_of``, root first.

    >>> subtree_ids(1, {1: None, 2: 1, 3: 2, 4: None})
    [1, 2, 3]
    """
    children: dict[int, list[int]] = {}
    for album_id, parent_id in parent_of.items():
        if parent_id is not None:
            children.setdefault(parent_id, []).append(album_id)
    ordered: list[int] = []
    stack = [root_id]
    while stack:
        current = stack.pop()
        if current in ordered:
            continue
        ordered.append(current)
        stack.extend(sorted(children.get(current, []), reverse=True))
    return ordered


def _depth_within(
    album_id: int, members: Collection[int], parent_of: Mapping[int, int | None]
) -> int:
    depth, seen = 0, {album_id}
    current = parent_of.get(album_id)
    while current is not None and current in members and current not in seen:
        seen.add(current)
        depth += 1
        current = parent_of.get(current)
    return depth


def purge_order(album_ids: Collection[int], parent_of: Mapping[int, int | None]) -> list[int]:
    """``album_ids`` deepest first, counting depth only within the set, so every album is deleted
    before its parent (``Album.parent`` is PROTECT).

    >>> purge_order([1, 2, 3], {1: None, 2: 1, 3: 2})
    [3, 2, 1]
    """
    members = set(album_ids)
    depth = {album_id: _depth_within(album_id, members, parent_of) for album_id in members}
    return sorted(members, key=lambda album_id: (-depth[album_id], album_id))


def purge_on(deleted_at: datetime) -> date:
    """UTC date on which a trashed item becomes eligible for the purge.

    >>> purge_on(datetime(2026, 9, 29, 23, 30, tzinfo=UTC))
    datetime.date(2026, 10, 29)
    """
    return (deleted_at + TRASH_RETENTION).astimezone(UTC).date()
