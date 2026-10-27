"""Give Liderança `owner` on the new scope `bible_videos` (specs/025-bible-videos FR-001).

Reason: Bible videos are managed by Admin and Liderança only, and Liderança must be able to
delete videos and remove places, so it gets `owner` rather than `manage` with a lowered DELETE.
Levels live in the role groups (spec 012 D-1), so code cannot grant them: Admin is `owner` of
every scope in code and needs nothing here, Mídia gets nothing. Same shape as 0010.

The permission row is get-or-created: Django creates `Meta.permissions` rows in `post_migrate`,
after every migration, so on a fresh database it may not exist yet while this runs.

The reverse removes the level from Liderança, restoring the matrix before this feature.
"""

from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps

ROLE = "leader"
OWNER = ("bible_videos__owner", "bible_videos: owner")


def _permission(apps: StateApps) -> object:
    content_type_model = apps.get_model("contenttypes", "ContentType")
    permission_model = apps.get_model("auth", "Permission")
    content_type, _ = content_type_model.objects.get_or_create(app_label="core", model="panelscope")
    permission, _ = permission_model.objects.get_or_create(
        content_type=content_type, codename=OWNER[0], defaults={"name": OWNER[1]}
    )
    return permission


def forward(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    group_model = apps.get_model("auth", "Group")
    for group in group_model.objects.filter(name=ROLE):
        group.permissions.add(_permission(apps))


def backward(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    group_model = apps.get_model("auth", "Group")
    for group in group_model.objects.filter(name=ROLE):
        group.permissions.remove(_permission(apps))


class Migration(migrations.Migration):
    dependencies = [("core", "0011_alter_panelscope_options")]

    operations = [migrations.RunPython(forward, backward)]
