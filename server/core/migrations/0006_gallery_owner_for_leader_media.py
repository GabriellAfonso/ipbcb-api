"""Raise Liderança and Mídia from `manage` to `owner` on scope `gallery`
(specs/013-gallery-write-api FR-003).

Reason: the requester decided, in feature 013, that the three roles build the gallery together
and may also delete in it — `DELETE /api/albums/{id}/cover/` now, deleting albums and photos in
feature 014, so 014 needs no permission change. Levels live in the role groups (spec 012 D-1),
so code cannot change them. 0005 is applied in production and must not be edited
(CLAUDE.md §5), hence this migration.

Only the highest level per scope is stored (0005's convention), so `gallery__manage` is swapped
for `gallery__owner`, not kept beside it. The permission rows are get-or-created, as in 0005:
Django creates `Meta.permissions` rows in `post_migrate`, after every migration, so on a fresh
database they may not exist yet while this runs.

The reverse swaps back, restoring 0005's matrix.

Verified against a restored production dump: pending (tasks T071).
"""

from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps

ROLES = ("leader", "media")
MANAGE = ("gallery__manage", "gallery: manage")
OWNER = ("gallery__owner", "gallery: owner")


def _permission(apps: StateApps, codename: str, name: str) -> object:
    content_type_model = apps.get_model("contenttypes", "ContentType")
    permission_model = apps.get_model("auth", "Permission")
    content_type, _ = content_type_model.objects.get_or_create(app_label="core", model="panelscope")
    permission, _ = permission_model.objects.get_or_create(
        content_type=content_type, codename=codename, defaults={"name": name}
    )
    return permission


def _swap(apps: StateApps, remove: tuple[str, str], add: tuple[str, str]) -> None:
    group_model = apps.get_model("auth", "Group")
    to_remove = _permission(apps, *remove)
    to_add = _permission(apps, *add)
    for group in group_model.objects.filter(name__in=ROLES):
        group.permissions.remove(to_remove)
        group.permissions.add(to_add)


def forward(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    _swap(apps, remove=MANAGE, add=OWNER)


def backward(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    _swap(apps, remove=OWNER, add=MANAGE)


class Migration(migrations.Migration):
    dependencies = [("core", "0005_seed_panel_roles")]

    operations = [migrations.RunPython(forward, backward)]
