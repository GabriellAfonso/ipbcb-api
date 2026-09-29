"""Small pure rules of the gallery: album names, photo names, full-order requests."""

from collections import Counter
from collections.abc import Collection, Sequence
from dataclasses import dataclass

from core.domain.exceptions import ValidationError

PHOTO_NAME_MAX_LENGTH = 100


def normalize_album_name(raw: str) -> str:
    """Trim an album name; a blank one is refused. Uniqueness compares the trimmed name.

    >>> normalize_album_name("  Retiros ")
    'Retiros'
    """
    name = raw.strip()
    if not name:
        raise ValidationError(f"O nome do álbum não pode ficar vazio (recebido: {raw!r}).")
    return name


def fit_photo_name(filename: str, max_length: int = PHOTO_NAME_MAX_LENGTH) -> str:
    """Cut a filename to ``max_length`` characters, keeping its extension.

    >>> fit_photo_name("a" * 120 + ".jpg")[-8:]
    'aaaa.jpg'
    """
    if len(filename) <= max_length:
        return filename
    stem, dot, extension = filename.rpartition(".")
    if not dot or len(extension) + 1 >= max_length:
        return filename[:max_length]
    return stem[: max_length - len(extension) - 1] + dot + extension


@dataclass(frozen=True)
class OrderDiff:
    """How a requested full order differs from the current set of siblings."""

    missing: list[int]
    unexpected: list[int]
    repeated: list[int]

    @property
    def is_exact(self) -> bool:
        return not (self.missing or self.unexpected or self.repeated)


def compare_order_ids(requested: Sequence[int], current: Collection[int]) -> OrderDiff:
    """Compare a requested order with the current siblings.

    >>> compare_order_ids([3, 1, 1], {1, 2})
    OrderDiff(missing=[2], unexpected=[3], repeated=[1])
    """
    counts = Counter(requested)
    current_set = set(current)
    return OrderDiff(
        missing=sorted(current_set - counts.keys()),
        unexpected=sorted(counts.keys() - current_set),
        repeated=sorted(item for item, count in counts.items() if count > 1),
    )
