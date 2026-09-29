"""Data migration 0003 numbers existing albums by name and photos by upload time
(specs/013-gallery-write-api FR-009).

0003 is reversible (its reverse is a no-op), so the test walks the real schema back to 0001,
creates rows there, and migrates forward.
"""

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

BEFORE = ("gallery", "0001_initial")
BACKFILL = ("gallery", "0003_backfill_positions")


def _migrate(target: tuple[str, str]) -> Any:
    executor = MigrationExecutor(connection)
    executor.migrate([target])
    return executor.loader.project_state(target).apps


@pytest.fixture
def apps_before() -> Iterator[Any]:
    yield _migrate(BEFORE)
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())


def _photo(apps: Any, album: Any, name: str, uploaded_at: datetime) -> Any:
    photo_model = apps.get_model("gallery", "Photo")
    photo = photo_model.objects.create(album=album, name=name, image=f"gallery/x/{name}")
    # auto_now_add ignores the value on create; set it afterwards.
    photo_model.objects.filter(pk=photo.pk).update(uploaded_at=uploaded_at)
    return photo


@pytest.mark.django_db(transaction=True)
class TestPositionBackfill:
    def test_albums_by_name_and_photos_by_upload_time(self, apps_before: Any) -> None:
        album_model = apps_before.get_model("gallery", "Album")
        album_c = album_model.objects.create(name="C")
        album_a = album_model.objects.create(name="A")
        album_b = album_model.objects.create(name="B")
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        late = _photo(apps_before, album_a, "late.jpg", start + timedelta(days=2))
        early = _photo(apps_before, album_a, "early.jpg", start)
        other = _photo(apps_before, album_b, "other.jpg", start + timedelta(days=5))

        apps = _migrate(BACKFILL)

        albums = apps.get_model("gallery", "Album").objects
        photos = apps.get_model("gallery", "Photo").objects
        assert [albums.get(pk=a.pk).position for a in (album_a, album_b, album_c)] == [0, 1, 2]
        assert all(albums.get(pk=a.pk).parent_id is None for a in (album_a, album_b, album_c))
        assert [photos.get(pk=p.pk).position for p in (early, late, other)] == [0, 1, 0]

    def test_rolls_back_to_0001_and_forward_again(self, apps_before: Any) -> None:
        _migrate(BACKFILL)
        _migrate(BEFORE)

        apps = _migrate(BACKFILL)

        assert apps.get_model("gallery", "Album").objects.count() == 0
