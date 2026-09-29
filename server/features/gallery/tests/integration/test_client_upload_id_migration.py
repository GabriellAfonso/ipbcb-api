"""``gallery 0006`` adds the nullable ``client_upload_id`` and its constraint without touching
existing photos, and rolls back cleanly (specs/016-photo-upload-idempotency R-09, quickstart §4).
The production-dump run is quickstart §4; this pins the shape."""

from collections.abc import Iterator

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

BEFORE = [("gallery", "0005_phototag")]
AFTER = [("gallery", "0006_photo_client_upload_id")]


def _migrate(targets: list[tuple[str, str]]) -> MigrationExecutor:
    executor = MigrationExecutor(connection)
    executor.migrate(targets)
    return MigrationExecutor(connection)


def _photo_columns() -> set[str]:
    with connection.cursor() as cursor:
        description = connection.introspection.get_table_description(cursor, "gallery_photo")
    return {column.name for column in description}


def _create_photo_before(executor: MigrationExecutor) -> int:
    apps = executor.loader.project_state(BEFORE).apps
    album = apps.get_model("gallery", "Album").objects.create(name="Retiro")
    photo = apps.get_model("gallery", "Photo").objects.create(
        album=album, name="IMG_0042.jpg", image="gallery/1/a.jpg"
    )
    return int(photo.pk)


@pytest.fixture
def back_to_leaf() -> Iterator[None]:
    yield
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())


@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("back_to_leaf")
class TestClientUploadIdMigration:
    def test_forward_keeps_existing_photos_with_no_id(self) -> None:
        photo_id = _create_photo_before(_migrate(BEFORE))

        executor = _migrate(AFTER)

        photo_model = executor.loader.project_state(AFTER).apps.get_model("gallery", "Photo")
        assert list(photo_model.objects.values_list("pk", "client_upload_id")) == [(photo_id, None)]

    def test_rollback_removes_the_column_and_keeps_the_rows(self) -> None:
        photo_id = _create_photo_before(_migrate(BEFORE))
        _migrate(AFTER)

        executor = _migrate(BEFORE)

        assert "client_upload_id" not in _photo_columns()
        photo_model = executor.loader.project_state(BEFORE).apps.get_model("gallery", "Photo")
        assert list(photo_model.objects.values_list("pk", flat=True)) == [photo_id]
