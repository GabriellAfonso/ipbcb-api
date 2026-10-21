"""Rename `Profile.is_member` to `Profile.member_access` (specs/022-access-requests R-01).

The `RenameField` below is HAND-WRITTEN ON PURPOSE and must never be regenerated.
`makemigrations` only detects a rename by asking interactively; run non-interactively it emits
RemoveField + AddField(default=False) instead, which SILENTLY REVOKES member access from every
account. `RenameField` is an `ALTER TABLE ... RENAME COLUMN` on PostgreSQL and SQLite: the values
stay where they are, and the reverse renames the column back.

Reason for the rename: `Profile.member` (the link to the church roll) and `is_member` (the gate on
member content) are independent, and the old name made people read the flag as "is linked to the
roll" (constitution §5 exception, compensating controls in specs/022-access-requests/quickstart.md).

Verified against a restored production dump, with the rollback run: pending (tasks T033).
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("accounts", "0005_profile_member")]

    operations = [
        migrations.RenameField(
            model_name="profile", old_name="is_member", new_name="member_access"
        ),
    ]
