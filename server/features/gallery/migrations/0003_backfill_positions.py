"""Number existing albums and photos (specs/013-gallery-write-api FR-009).

Reason: 0002 adds `position` to `Album` and `Photo` with default 0, and reads now order by
`position, id`. Left at 0, every existing album and photo would fall back to id order, which is
neither the old album order (by name) nor the old photo order (by upload time). This keeps what
members saw before the deploy: every album is a root after 0002, numbered by `name`; each album's
photos are numbered by `(uploaded_at, id)`. Both from 0.

The reverse is a no-op: 0001's schema has no `position` column, and rolling 0002 back drops it.

Verified against a restored production dump: pending (tasks T071).
"""

from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def _number_albums(apps: StateApps) -> None:
    album_model = apps.get_model("gallery", "Album")
    albums = list(album_model.objects.order_by("name", "id"))
    for index, album in enumerate(albums):
        album.position = index
    album_model.objects.bulk_update(albums, ["position"])


def _number_photos(apps: StateApps) -> None:
    photo_model = apps.get_model("gallery", "Photo")
    photos = list(photo_model.objects.order_by("album_id", "uploaded_at", "id"))
    next_position: dict[int, int] = {}
    for photo in photos:
        photo.position = next_position.get(photo.album_id, 0)
        next_position[photo.album_id] = photo.position + 1
    photo_model.objects.bulk_update(photos, ["position"], batch_size=500)


def forward(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    _number_albums(apps)
    _number_photos(apps)


class Migration(migrations.Migration):
    dependencies = [("gallery", "0002_album_tree_positions_covers")]

    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
