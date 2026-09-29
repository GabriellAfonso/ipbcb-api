"""Regression: the files of trashed gallery items stop being served to members and stay readable
to owners (specs/014-gallery-trash-sync FR-024–FR-030, amending spec 009).

Lives with the gallery tests on purpose: it builds gallery rows, and features never import each
other; it reaches the media check only through its URL.
"""

from pathlib import Path

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from pytest_django.fixtures import SettingsWrapper
from rest_framework.test import APIClient

from conftest import make_member_client
from core.domain.access import Role
from features.gallery.models.gallery import Album, Photo
from features.gallery.tests.integration.helpers import gallery_manager

REDIRECT = "X-Accel-Redirect"


@pytest.fixture
def served_root(media_root: Path, settings: SettingsWrapper) -> Path:
    """Production delivery (X-Accel-Redirect) over a temporary MEDIA_ROOT."""
    settings.DEBUG = False
    return media_root


def _write(root: Path, name: str) -> str:
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"\xff\xd8jpeg")
    return name


def _get(client: APIClient, name: str) -> int:
    return int(client.get(f"/ipbcb/media/{name}").status_code)


def _trash(photo: Photo) -> None:
    Photo.all_objects.filter(pk=photo.pk).update(deleted_at=timezone.now())


@pytest.mark.django_db
class TestTrashedPhotoFiles:
    def test_member_404_owner_200_for_original_and_thumbnail(self, served_root: Path) -> None:
        album = Album.objects.create(name="Culto")
        image = _write(served_root, f"gallery/{album.pk}/9b1e.jpg")
        thumb = _write(served_root, f"gallery/thumbs/{album.pk}/c4d0.jpg")
        photo = Photo.objects.create(album=album, name="a.jpg", image=image, thumbnail=thumb)
        member, _ = make_member_client()
        owner = gallery_manager(Role.MEDIA)
        assert (_get(member, image), _get(member, thumb)) == (200, 200)

        owner.delete(f"/api/photos/{photo.pk}/")

        assert (_get(member, image), _get(member, thumb)) == (404, 404)
        response = owner.get(f"/ipbcb/media/{image}")
        assert response.status_code == 200 and REDIRECT in response

    def test_photo_trashed_with_its_album_and_the_album_cover(self, served_root: Path) -> None:
        cover = _write(served_root, "gallery/covers/1/3f2a.jpg")
        album = Album.objects.create(name="Culto", cover_image=cover)
        image = _write(served_root, f"gallery/{album.pk}/9b1e.jpg")
        Photo.objects.create(album=album, name="a.jpg", image=image)
        member, _ = make_member_client()

        gallery_manager().delete(f"/api/albums/{album.pk}/")

        assert (_get(member, image), _get(member, cover)) == (404, 404)

    def test_pre_013_path_is_covered(self, served_root: Path) -> None:
        album = Album.objects.create(name="Retiro 2025")
        legacy = _write(served_root, "gallery/retiro-2025/IMG_0042.jpg")
        photo = Photo.objects.create(album=album, name="IMG_0042.jpg", image=legacy)
        member, _ = make_member_client()

        _trash(photo)

        assert _get(member, legacy) == 404

    def test_live_and_orphan_files_keep_the_member_rule(self, served_root: Path) -> None:
        album = Album.objects.create(name="Culto")
        live = _write(served_root, f"gallery/{album.pk}/live.jpg")
        Photo.objects.create(album=album, name="live.jpg", image=live)
        orphan = _write(served_root, "gallery/old-album/orphan.jpg")
        member, _ = make_member_client()

        assert (_get(member, live), _get(member, orphan)) == (200, 200)

    def test_one_gallery_lookup_per_request_and_none_elsewhere(self, served_root: Path) -> None:
        album = Album.objects.create(name="Culto")
        image = _write(served_root, f"gallery/{album.pk}/q.jpg")
        other = _write(served_root, "profiles/someone/p.png")
        Photo.objects.create(album=album, name="q.jpg", image=image)
        member, _ = make_member_client()

        with CaptureQueriesContext(connection) as gallery_request:
            _get(member, image)
        with CaptureQueriesContext(connection) as profile_request:
            _get(member, other)

        assert _gallery_table_queries(gallery_request) == 1  # FR-027
        assert _gallery_table_queries(profile_request) == 0  # FR-028


def _gallery_table_queries(captured: CaptureQueriesContext) -> int:
    return sum(1 for query in captured.captured_queries if '"gallery_' in query["sql"])
