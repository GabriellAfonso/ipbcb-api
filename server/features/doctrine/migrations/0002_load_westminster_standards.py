"""Load the Westminster Standards into the database (specs/027-doctrine-database FR-008, R-04).

Reason: the Shorter Catechism, the Larger Catechism and the Confession of Faith used to be JSON
files read and validated when the server started (specs/019-doctrine-documents). The user wanted
study content in the database instead of tied to the code, so the reviewed files were moved,
unchanged in content, to ``data/`` beside this migration. A data migration (not a SQL dump) so the
load runs on the deploy's ``migrate``, goes through the same validation as before and depends on
no database id.

The files never change once applied: a correction or a new document is a new data migration,
with its files in a subdirectory of ``data/`` (the loader reads only the top level here).
``edition`` and ``year`` are left empty on purpose; the user wants them taken from the IPB site
only, and it had no page for the symbols of faith on 2026-10-27.

A file that breaks a doctrine rule raises ``DoctrineDataError`` inside the migration's
transaction, so nothing is loaded and the server is never started on a partial set.

The reverse deletes the rows whose slugs these files hold.
"""

from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps

from features.doctrine.loading import DOCTRINE_DATA_DIR, load_doctrine_documents, stored_content


def forward(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    standard_model = apps.get_model("doctrine", "DoctrineStandard")
    standard_model.objects.bulk_create(
        standard_model(
            slug=document.slug,
            title=document.title,
            kind=document.kind,
            position=document.position,
            edition="",
            year=None,
            content=stored_content(document),
        )
        for document in load_doctrine_documents(DOCTRINE_DATA_DIR)
    )


def backward(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    standard_model = apps.get_model("doctrine", "DoctrineStandard")
    slugs = [document.slug for document in load_doctrine_documents(DOCTRINE_DATA_DIR)]
    standard_model.objects.filter(slug__in=slugs).delete()


class Migration(migrations.Migration):
    dependencies = [("doctrine", "0001_initial")]

    operations = [migrations.RunPython(forward, backward)]
