from collections.abc import Collection, Sequence

from core.domain.exceptions import OrderMismatchError
from features.gallery.domain.gallery_rules import compare_order_ids


def ensure_exact_order(requested: Sequence[int], current: Collection[int]) -> None:
    """Refuse a full-order request that does not list every current sibling exactly once.

    >>> ensure_exact_order([2, 1], [1, 2])
    """
    diff = compare_order_ids(requested, current)
    if not diff.is_exact:
        raise OrderMismatchError(diff.missing, diff.unexpected, diff.repeated)
