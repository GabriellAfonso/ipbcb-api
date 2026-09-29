import logging
from functools import partial
from uuid import UUID

from django.db import transaction

from core.time.clock import Clock
from features.gallery.domain.trash_rules import MARK_RETENTION, TRASH_RETENTION
from features.gallery.dtos.trash_dtos import PurgedBatch, PurgeReport
from features.gallery.repositories.interfaces import (
    DeletionMarkRepository,
    GalleryFileStorage,
    TrashRepository,
)

logger = logging.getLogger("features.gallery")


class GalleryPurgeService:
    """Deletes for good what has been in the trash longer than the retention, files included.

    One transaction per batch, so a failing batch rolls back alone and the run goes on; files are
    removed only once their batch's rows are committed, and a missing file is not an error
    (specs/014-gallery-trash-sync research R-09). Removing a row never removes its deletion mark;
    marks past their own retention are dropped in a separate step.
    """

    def __init__(
        self,
        trash_repository: TrashRepository,
        mark_repository: DeletionMarkRepository,
        file_storage: GalleryFileStorage,
        clock: Clock,
    ) -> None:
        self._trash = trash_repository
        self._marks = mark_repository
        self._storage = file_storage
        self._clock = clock

    def purge_expired(self) -> PurgeReport:
        """Purge every batch older than ``TRASH_RETENTION``, then expire old marks. Idempotent.

        >>> service.purge_expired()
        PurgeReport(batches=1, albums=3, photos=12, skipped_batch_ids=[], marks_expired=0)
        """
        now = self._clock.now()
        purged: list[PurgedBatch] = []
        skipped: list[UUID] = []
        for batch_id in self._trash.expired_batch_ids(now - TRASH_RETENTION):
            result = self._purge_one(batch_id)
            if result is None:
                skipped.append(batch_id)
            else:
                purged.append(result)
        report = PurgeReport(
            batches=len(purged),
            albums=sum(len(p.album_ids) for p in purged),
            photos=sum(len(p.photo_ids) for p in purged),
            skipped_batch_ids=skipped,
            marks_expired=self._marks.expire(now - MARK_RETENTION),
        )
        logger.info("gallery_purge_summary", extra=_summary_fields(report))
        return report

    def _purge_one(self, batch_id: UUID) -> PurgedBatch | None:
        try:
            with transaction.atomic():
                purged = self._trash.purge_batch(batch_id)
                for name in purged.file_names:
                    transaction.on_commit(partial(self._storage.delete, name), robust=True)
        except Exception as exc:  # one bad batch must not stop the run (spec FR-033)
            logger.warning(
                "gallery_purge_skipped", extra={"batch": str(batch_id), "error": type(exc).__name__}
            )
            return None
        logger.info("gallery_purged", extra=_purged_fields(batch_id, purged))
        return purged


def _purged_fields(batch_id: UUID, purged: PurgedBatch) -> dict[str, object]:
    return {
        "batch": str(batch_id),
        "actor_id": None,
        "album_count": len(purged.album_ids),
        "photo_count": len(purged.photo_ids),
    }


def _summary_fields(report: PurgeReport) -> dict[str, object]:
    return {
        "batches": report.batches,
        "albums": report.albums,
        "photos": report.photos,
        "skipped": len(report.skipped_batch_ids),
        "marks_expired": report.marks_expired,
    }
