import io
import re
from pathlib import Path

import pytest

from features.gallery.repositories.gallery_file_storage import DefaultStorageGalleryFileStorage

STORAGE = DefaultStorageGalleryFileStorage()
_HEX = "[0-9a-f]{32}"


class TestSave:
    def test_original_goes_under_the_album_with_the_given_extension(self, media_root: Path) -> None:
        name = STORAGE.save_original(7, "png", io.BytesIO(b"png-bytes"))

        assert re.fullmatch(rf"gallery/7/{_HEX}\.png", name)
        assert (media_root / name).read_bytes() == b"png-bytes"

    def test_original_is_written_from_the_start_of_the_stream(self, media_root: Path) -> None:
        stream = io.BytesIO(b"whole")
        stream.read()

        name = STORAGE.save_original(7, "jpg", stream)

        assert (media_root / name).read_bytes() == b"whole"

    def test_thumbnail(self, media_root: Path) -> None:
        name = STORAGE.save_thumbnail(7, b"jpeg")

        assert re.fullmatch(rf"gallery/thumbs/7/{_HEX}\.jpg", name)

    def test_cover(self, media_root: Path) -> None:
        name = STORAGE.save_cover(9, b"jpeg")

        assert re.fullmatch(rf"gallery/covers/9/{_HEX}\.jpg", name)

    def test_two_saves_never_collide(self, media_root: Path) -> None:
        assert STORAGE.save_thumbnail(7, b"a") != STORAGE.save_thumbnail(7, b"b")


class TestReadDeleteUrl:
    def test_open_reads_back(self, media_root: Path) -> None:
        name = STORAGE.save_cover(1, b"cover")

        with STORAGE.open(name) as stored:
            assert stored.read() == b"cover"

    def test_open_missing_raises(self, media_root: Path) -> None:
        with pytest.raises(FileNotFoundError):
            STORAGE.open("gallery/1/missing.jpg")

    def test_delete_removes_and_tolerates_missing(self, media_root: Path) -> None:
        name = STORAGE.save_cover(1, b"cover")

        STORAGE.delete(name)
        STORAGE.delete(name)

        assert not (media_root / name).exists()

    def test_url_is_under_the_media_prefix(self, media_root: Path) -> None:
        assert STORAGE.url("gallery/7/x.jpg").endswith("/media/gallery/7/x.jpg")
