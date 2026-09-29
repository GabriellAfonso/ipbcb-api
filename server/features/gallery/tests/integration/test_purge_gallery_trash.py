"""The purge command on real rows and files (specs/014-gallery-trash-sync US5, FR-031–FR-033)."""

from datetime import timedelta
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.utils import timezone

from features.gallery.models.gallery import Album, Photo
from features.gallery.models.trash import GalleryDeletionBatch, GalleryDeletionMark
from features.gallery.tests.integration.helpers import gallery_manager
from features.gallery.tests.support import CaptureOnCommit


def _file(root: Path, name: str) -> str:
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"jpeg")
    return name


def _age(days: int, **batch_filter: object) -> None:
    GalleryDeletionBatch.objects.filter(**batch_filter).update(
        deleted_at=timezone.now() - timedelta(days=days)
    )


def _purge() -> str:
    out = StringIO()
    call_command("purge_gallery_trash", stdout=out)
    return out.getvalue()


@pytest.mark.django_db
class TestPurgeCommand:
    def test_regression_album_tree_is_purged_despite_protect(
        self, media_root: Path, django_capture_on_commit_callbacks: CaptureOnCommit
    ) -> None:
        a = Album.objects.create(name="A", cover_image=_file(media_root, "gallery/covers/a/c.jpg"))
        b = Album.objects.create(name="B", parent=a)
        c = Album.objects.create(name="C", parent=b)
        files = [_file(media_root, f"gallery/{album.pk}/{album.name}.jpg") for album in (a, b, c)]
        for album, name in zip((a, b, c), files):
            Photo.objects.create(album=album, name="p.jpg", image=name)
        gallery_manager().delete(f"/api/albums/{a.pk}/")
        _age(31)

        # Files go only once the batch's transaction commits.
        with django_capture_on_commit_callbacks(execute=True):
            output = _purge()

        assert "purged 1 batches (3 albums, 3 photos); skipped 0" in output
        assert not Album.all_objects.exists() and not Photo.all_objects.exists()
        assert not GalleryDeletionBatch.objects.exists()
        assert all(not (media_root / name).exists() for name in [*files, "gallery/covers/a/c.jpg"])
        assert GalleryDeletionMark.objects.count() == 6

    def test_missing_file_is_not_an_error(self, media_root: Path) -> None:
        album = Album.objects.create(name="A")
        photo = Photo.objects.create(album=album, name="p.jpg", image="gallery/1/gone.jpg")
        gallery_manager().delete(f"/api/photos/{photo.pk}/")
        _age(31)

        assert "purged 1 batches" in _purge()
        assert not Photo.all_objects.filter(pk=photo.pk).exists()

    def test_recent_batch_is_untouched_and_second_run_is_a_no_op(self, media_root: Path) -> None:
        album = Album.objects.create(name="A")
        photo = Photo.objects.create(
            album=album, name="p.jpg", image=_file(media_root, "gallery/1/p.jpg")
        )
        gallery_manager().delete(f"/api/photos/{photo.pk}/")
        _age(29)

        assert "purged 0 batches" in _purge()
        assert Photo.all_objects.filter(pk=photo.pk).exists()
        assert (media_root / "gallery/1/p.jpg").exists()

    def test_blocked_batch_is_skipped_then_retried(self, media_root: Path) -> None:
        album = Album.objects.create(name="A")
        photo = Photo.objects.create(album=album, name="p.jpg", image="gallery/1/p.jpg")
        client = gallery_manager()
        client.delete(f"/api/photos/{photo.pk}/")
        client.delete(f"/api/albums/{album.pk}/")
        # The photo's own batch is not due yet, so its row still holds the album (PROTECT).
        _age(40, root_kind="album")
        _age(10, root_kind="photo")

        first = _purge()

        assert "purged 0 batches" in first and "skipped 1" in first
        assert Album.all_objects.filter(pk=album.pk).exists()

        _age(41, root_kind="photo")
        assert "purged 2 batches" in _purge()
        assert not Album.all_objects.exists() and not Photo.all_objects.exists()
