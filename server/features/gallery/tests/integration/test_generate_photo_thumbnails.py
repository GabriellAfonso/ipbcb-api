"""The one-off thumbnail backfill (specs/013-gallery-write-api US7)."""

from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command

from features.gallery.models.gallery import Album, Photo
from features.gallery.tests.support import stored_name
from features.gallery.tests.integration.helpers import decoded_size, image_file


def _run() -> str:
    output = StringIO()
    call_command("generate_photo_thumbnails", stdout=output)
    return output.getvalue().strip()


@pytest.mark.django_db
class TestGeneratePhotoThumbnails:
    def test_fills_readable_skips_missing_and_is_idempotent(self, media_root: Path) -> None:
        album = Album.objects.create(name="Culto")
        original = media_root / "gallery" / "culto" / "IMG_0042.jpg"
        original.parent.mkdir(parents=True)
        original.write_bytes(image_file(size=(3000, 2000)).getvalue())
        readable = Photo.objects.create(
            album=album, name="IMG_0042.jpg", image="gallery/culto/IMG_0042.jpg"
        )
        missing = Photo.objects.create(album=album, name="gone.jpg", image="gallery/culto/gone.jpg")

        first = _run()

        readable.refresh_from_db()
        assert first == f"filled 1, skipped 1: ids [{missing.pk}]"
        assert stored_name(readable.thumbnail).startswith(f"gallery/thumbs/{album.pk}/")
        assert decoded_size((media_root / stored_name(readable.thumbnail)).read_bytes()) == (
            1000,
            667,
        )
        assert _run() == f"filled 0, skipped 1: ids [{missing.pk}]"
