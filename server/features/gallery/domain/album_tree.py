"""Pure rules over the album tree: cycle detection, tree order and cover inheritance.

No I/O — the service loads the whole (small) album table once and hands it here. Every walk
keeps a visited set, so a cycle that reached the database by any path cannot hang a request
(specs/013-gallery-write-api/research.md R-02, R-06).
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class AlbumNode:
    """The fields of an album the tree rules need."""

    id: int
    parent_id: int | None
    position: int
    has_own_cover: bool


def find_cycle(
    album_id: int, new_parent_id: int | None, parent_of: Mapping[int, int | None]
) -> list[int] | None:
    """Chain from ``new_parent_id`` up to ``album_id`` if the move would build a cycle.

    >>> find_cycle(3, 9, {3: None, 5: 3, 9: 5})
    [9, 5, 3]
    """
    chain: list[int] = []
    current = new_parent_id
    while current is not None and current not in chain:
        chain.append(current)
        if current == album_id:
            return chain
        current = parent_of.get(current)
    return None


def _sort_key(node: AlbumNode) -> tuple[int, int]:
    return (node.position, node.id)


def _children_by_parent(nodes: Iterable[AlbumNode]) -> dict[int | None, list[AlbumNode]]:
    """Children of each parent, sorted by ``(position, id)``; roots under ``None``."""
    children: dict[int | None, list[AlbumNode]] = {}
    for node in nodes:
        children.setdefault(node.parent_id, []).append(node)
    for siblings in children.values():
        siblings.sort(key=_sort_key)
    return children


def tree_order(nodes: Sequence[AlbumNode]) -> list[int]:
    """Album ids in pre-order, siblings by ``(position, id)``.

    Albums unreachable from a root (a cycle, a dangling parent) come last, so none disappears.

    >>> tree_order([AlbumNode(1, None, 1, False), AlbumNode(2, None, 0, False),
    ...             AlbumNode(3, 1, 0, False)])
    [2, 1, 3]
    """
    children = _children_by_parent(nodes)
    ordered: list[int] = []
    visited: set[int] = set()
    stack = list(reversed(children.get(None, [])))
    while stack:
        node = stack.pop()
        if node.id in visited:
            continue
        visited.add(node.id)
        ordered.append(node.id)
        stack.extend(reversed(children.get(node.id, [])))
    orphans = sorted((n for n in nodes if n.id not in visited), key=_sort_key)
    return ordered + [node.id for node in orphans]


def resolve_cover_sources(nodes: Sequence[AlbumNode]) -> dict[int, int | None]:
    """For each album, the album its shown cover comes from, or ``None``.

    Own cover first; otherwise the first descendant with one, depth-first. Resolving each child
    before its parent makes "first child whose source is set" equal to that pre-order search.

    >>> resolve_cover_sources([AlbumNode(1, None, 0, False), AlbumNode(2, 1, 0, True)])
    {1: 2, 2: 2}
    """
    children = _children_by_parent(nodes)
    sources: dict[int, int | None] = {}
    for node in nodes:
        _resolve(node, children, sources, set())
    return sources


def resolved_cover_names(
    nodes: Sequence[AlbumNode], cover_names: Mapping[int, str]
) -> dict[int, str | None]:
    """For each album, the file name of the cover it shows, or ``None``.

    >>> resolved_cover_names([AlbumNode(1, None, 0, False), AlbumNode(2, 1, 0, True)],
    ...                      {2: "gallery/covers/2/a.jpg"})
    {1: 'gallery/covers/2/a.jpg', 2: 'gallery/covers/2/a.jpg'}
    """
    sources = resolve_cover_sources(nodes)
    return {
        album_id: (cover_names.get(source) if source is not None else None)
        for album_id, source in sources.items()
    }


def changed_cover_albums(
    before: Mapping[int, str | None], after: Mapping[int, str | None]
) -> set[int]:
    """Albums present in ``after`` whose shown cover file differs from ``before`` (or that are
    new). Compares file names, not source ids, so replacing an own cover counts
    (specs/014-gallery-trash-sync research R-06).

    >>> changed_cover_albums({1: "a.jpg", 2: "a.jpg"}, {1: "b.jpg", 2: "a.jpg"})
    {1}
    """
    return {
        album_id
        for album_id, cover in after.items()
        if album_id not in before or before[album_id] != cover
    }


def _resolve(
    node: AlbumNode,
    children: Mapping[int | None, list[AlbumNode]],
    sources: dict[int, int | None],
    in_progress: set[int],
) -> int | None:
    if node.id in sources:
        return sources[node.id]
    if node.id in in_progress:
        return None
    in_progress.add(node.id)
    source = (
        node.id if node.has_own_cover else _first_child_source(node, children, sources, in_progress)
    )
    sources[node.id] = source
    return source


def _first_child_source(
    node: AlbumNode,
    children: Mapping[int | None, list[AlbumNode]],
    sources: dict[int, int | None],
    in_progress: set[int],
) -> int | None:
    for child in children.get(node.id, []):
        source = _resolve(child, children, sources, in_progress)
        if source is not None:
            return source
    return None
