"""Record the file size of every gallery item stored without one. Run once at the deploy of
feature 023; running it again changes nothing (specs/023-gallery-videos FR-024)."""

from typing import Any

from dependency_injector.wiring import Provide, inject
from django.core.management.base import BaseCommand

from config.di import Container
from features.gallery.dtos.gallery_dtos import FileSizeBackfillReport
from features.gallery.services.gallery_service import GalleryService


@inject
def _backfill(
    gallery_service: GalleryService = Provide[Container.gallery_service],
) -> FileSizeBackfillReport:
    return gallery_service.fill_missing_file_sizes()


def size_summary_line(report: FileSizeBackfillReport) -> str:
    """>>> size_summary_line(FileSizeBackfillReport(filled=3, skipped_ids=[7]))
    'filled 3, skipped 1: ids [7]'
    """
    return f"filled {report.filled}, skipped {len(report.skipped_ids)}: ids {report.skipped_ids}"


class Command(BaseCommand):
    help = "Record the file size of every gallery item that has none."

    def handle(self, *args: Any, **options: Any) -> None:
        self.stdout.write(size_summary_line(_backfill()))
