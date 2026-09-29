"""Thumbnail every gallery photo that has none. Run once at the deploy of feature 013; running
it again changes nothing (specs/013-gallery-write-api FR-019b)."""

from typing import Any

from dependency_injector.wiring import Provide, inject
from django.core.management.base import BaseCommand

from config.di import Container
from features.gallery.dtos.gallery_dtos import ThumbnailBackfillReport
from features.gallery.services.gallery_service import GalleryService


@inject
def _backfill(
    gallery_service: GalleryService = Provide[Container.gallery_service],
) -> ThumbnailBackfillReport:
    return gallery_service.fill_missing_thumbnails()


def summary_line(report: ThumbnailBackfillReport) -> str:
    """>>> summary_line(ThumbnailBackfillReport(filled=3, skipped_ids=[7]))
    'filled 3, skipped 1: ids [7]'
    """
    return f"filled {report.filled}, skipped {len(report.skipped_ids)}: ids {report.skipped_ids}"


class Command(BaseCommand):
    help = "Generate the thumbnail of every gallery photo that has none."

    def handle(self, *args: Any, **options: Any) -> None:
        self.stdout.write(summary_line(_backfill()))
