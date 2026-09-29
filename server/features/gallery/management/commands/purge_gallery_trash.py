"""Delete for good what has been in the gallery trash for more than 30 days, files included.
Run daily by a host cron on the production server; idempotent, so a missed or doubled run is
harmless (specs/014-gallery-trash-sync FR-031, research R-10)."""

from typing import Any

from dependency_injector.wiring import Provide, inject
from django.core.management.base import BaseCommand

from config.di import Container
from features.gallery.dtos.trash_dtos import PurgeReport
from features.gallery.services.gallery_purge_service import GalleryPurgeService


@inject
def _purge(
    purge_service: GalleryPurgeService = Provide[Container.gallery_purge_service],
) -> PurgeReport:
    return purge_service.purge_expired()


def summary_line(report: PurgeReport) -> str:
    """>>> summary_line(PurgeReport(batches=3, albums=2, photos=45, skipped_batch_ids=[],
    ...                             marks_expired=12))
    'purged 3 batches (2 albums, 45 photos); skipped 0: []; expired 12 marks'
    """
    skipped = [str(batch_id) for batch_id in report.skipped_batch_ids]
    return (
        f"purged {report.batches} batches ({report.albums} albums, {report.photos} photos); "
        f"skipped {len(skipped)}: {skipped}; expired {report.marks_expired} marks"
    )


class Command(BaseCommand):
    help = "Purge gallery albums and photos that have been in the trash for more than 30 days."

    def handle(self, *args: Any, **options: Any) -> None:
        # Exit code 0 even with skips: a skipped batch is retried by the next daily run, and a
        # failing exit would only make a scheduler retry in a loop.
        self.stdout.write(summary_line(_purge()))
