"""Turn every `Profile.is_admin=True` into membership of the Admin role (specs/012-feature-role-permissions).

Reason: access to the management panel moved from the `is_admin` flag to roles (Django groups).
Whoever managed the panel before the deploy must still manage it after, with no manual step
(spec FR-023, SC-001). Profiles with `is_admin=False` get no role. The column itself is dropped
by the next, generated migration.

One bulk insert into the user-group table; `ignore_conflicts` keeps a re-run, or a user already
added to the group by hand, from failing.

Irreversible on purpose: the rollback was dropped by the requester. A no-op reverse would let a
rollback re-add `is_admin` as `False` for everyone without complaint; recovery is the
pre-deploy dump.

Verified against a restored production dump: pending (tasks T037).
"""

from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps

ADMIN_GROUP = "admin"


def forward(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    group_model = apps.get_model("auth", "Group")
    profile_model = apps.get_model("accounts", "Profile")
    membership_model = apps.get_model("accounts", "User").groups.through

    # core.0005 creates it; get-or-create anyway so a group deleted by hand before the deploy
    # cannot make the conversion fail halfway through the release.
    admin_group, _ = group_model.objects.get_or_create(name=ADMIN_GROUP)
    admin_user_ids = profile_model.objects.filter(is_admin=True).values_list("user_id", flat=True)
    membership_model.objects.bulk_create(
        [membership_model(user_id=user_id, group_id=admin_group.pk) for user_id in admin_user_ids],
        ignore_conflicts=True,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_remove_profile_active"),
        ("core", "0005_seed_panel_roles"),
    ]

    operations = [migrations.RunPython(forward)]
