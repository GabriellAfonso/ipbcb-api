from collections.abc import Sequence
from datetime import datetime

from core.time.clock import Clock
from features.gallery.domain.trash_rules import TrashedItemKind
from features.gallery.models.trash import GalleryDeletionMark


class DeletionMarkRepositoryImpl:
    """The ids the change feed reports as deleted. Independent of the rows: a mark outlives the
    purge of its row (specs/014-gallery-trash-sync research R-08)."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock

    def upsert(self, kind: TrashedItemKind, ids: Sequence[int]) -> None:
        """One mark per id, dated now; an id deleted again keeps one mark with the new date.

        >>> repository.upsert(TrashedItemKind.PHOTO, [301, 302])
        """
        now = self._clock.now()
        marks = [GalleryDeletionMark(kind=kind.value, object_id=i, deleted_at=now) for i in ids]
        GalleryDeletionMark.objects.bulk_create(
            marks,
            update_conflicts=True,
            unique_fields=["kind", "object_id"],
            update_fields=["deleted_at"],
        )

    def remove(self, kind: TrashedItemKind, ids: Sequence[int]) -> None:
        """Forget the marks of restored rows. >>> repository.remove(TrashedItemKind.ALBUM, [7])"""
        GalleryDeletionMark.objects.filter(kind=kind.value, object_id__in=ids).delete()

    def ids_since(self, kind: TrashedItemKind, since: datetime) -> list[int]:
        """Ids deleted strictly after ``since``, ascending.

        >>> repository.ids_since(TrashedItemKind.PHOTO, cursor_instant)
        [301, 302]
        """
        marks = GalleryDeletionMark.objects.filter(kind=kind.value, deleted_at__gt=since)
        return sorted(marks.values_list("object_id", flat=True))

    def expire(self, before: datetime) -> int:
        """Drop marks deleted before ``before``; returns how many.

        >>> repository.expire(now - MARK_RETENTION)
        12
        """
        deleted, _ = GalleryDeletionMark.objects.filter(deleted_at__lt=before).delete()
        return deleted
