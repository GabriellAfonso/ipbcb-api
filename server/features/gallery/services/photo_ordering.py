from collections.abc import Sequence

from features.gallery.domain.album_tree import AlbumNode, tree_order
from features.gallery.dtos.gallery_dtos import AlbumRecord, PhotoView


def order_photos_by_tree(
    photos: Sequence[PhotoView], records: Sequence[AlbumRecord]
) -> list[PhotoView]:
    """Photos by the tree order of their album, keeping each album's own (position, id) order.
    Shared by the photo list and the change feed, so both return the same order.

    >>> [p.album_id for p in order_photos_by_tree(photos, records)]
    [2, 2, 7]
    """
    nodes = [AlbumNode(r.id, r.parent_id, r.position, bool(r.cover_name)) for r in records]
    rank = {album_id: index for index, album_id in enumerate(tree_order(nodes))}
    return sorted(photos, key=lambda photo: rank.get(photo.album_id, len(rank)))
