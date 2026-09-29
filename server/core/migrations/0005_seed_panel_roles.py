"""Create the three panel roles already holding their levels (specs/012-feature-role-permissions).

Reason: access to the management panel moved from `Profile.is_admin` to roles — Django groups
holding scope permissions. The roles must exist with their levels the moment the deploy
finishes. A Liderança or Mídia group that exists but holds nothing denies every request, and
nothing in the response says why (spec FR-025).

Why this migration creates the permission rows itself: Django creates the rows declared in
`Meta.permissions` (here, `core.PanelScope`, migration 0004) in a `post_migrate` signal, which
runs after every migration. On a fresh database — tests, a new environment — they do not exist
yet while this runs, and depending on 0004 does not change that. Looking them up would leave
the groups empty with no error. Get-or-create is safe against the later `post_migrate` pass,
which get-or-creates the same rows.

Why the matrix is written out here instead of imported: a migration must keep meaning what it
meant when it ran, whatever the application code says later. Admin holds no stored permission:
it is `owner` of every scope in code.

The reverse is a no-op: the forward pass is get-or-create, so running it again after a rollback
yields the same rows.

Verified against a restored production dump: pending (tasks T037).
"""

from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps

SCOPE_PERMISSIONS = [
    ("members__view", "members: view"),
    ("members__manage", "members: manage"),
    ("members__owner", "members: owner"),
    ("schedule__view", "schedule: view"),
    ("schedule__manage", "schedule: manage"),
    ("schedule__owner", "schedule: owner"),
    ("songs__view", "songs: view"),
    ("songs__manage", "songs: manage"),
    ("songs__owner", "songs: owner"),
    ("gallery__view", "gallery: view"),
    ("gallery__manage", "gallery: manage"),
    ("gallery__owner", "gallery: owner"),
    ("events__view", "events: view"),
    ("events__manage", "events: manage"),
    ("events__owner", "events: owner"),
    ("notices__view", "notices: view"),
    ("notices__manage", "notices: manage"),
    ("notices__owner", "notices: owner"),
    ("reports_hymnal_history__view", "reports.hymnal_history: view"),
    ("reports_hymnal_history__manage", "reports.hymnal_history: manage"),
    ("reports_hymnal_history__owner", "reports.hymnal_history: owner"),
]

# Only the highest level per scope is stored; lower ones follow from the ordering.
ROLE_PERMISSIONS = {
    "admin": [],
    "leader": [
        "members__manage",
        "schedule__manage",
        "songs__manage",
        "gallery__manage",
        "events__manage",
        "notices__manage",
        "reports_hymnal_history__view",
    ],
    "media": [
        "gallery__manage",
        "events__manage",
        "notices__manage",
        "reports_hymnal_history__view",
    ],
}


def _ensure_permissions(apps: StateApps) -> dict[str, object]:
    content_type_model = apps.get_model("contenttypes", "ContentType")
    permission_model = apps.get_model("auth", "Permission")
    content_type, _ = content_type_model.objects.get_or_create(app_label="core", model="panelscope")
    permissions: dict[str, object] = {}
    for codename, name in SCOPE_PERMISSIONS:
        permission, _ = permission_model.objects.get_or_create(
            content_type=content_type, codename=codename, defaults={"name": name}
        )
        permissions[codename] = permission
    return permissions


def forward(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    group_model = apps.get_model("auth", "Group")
    permissions = _ensure_permissions(apps)
    for role_name, codenames in ROLE_PERMISSIONS.items():
        group, _ = group_model.objects.get_or_create(name=role_name)
        group.permissions.add(*(permissions[codename] for codename in codenames))


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0004_panelscope"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
