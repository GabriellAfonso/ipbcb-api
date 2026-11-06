"""Add the 2026 lesson on Atos, the opening of Act 5 (specs/026-sunday-school FR-022, research R-08).

Reason: this lesson is given on 2026-11-08, after ``0002_load_2026_lessons`` ran in production,
and was converted from its PDF outline ("Roteiro Ato 5"). It lives in its own folder,
``data/0005_load_atos/``. It carries the date, given by the user as official; the teacher is not
known yet, so it stays empty. Published, no author.

It goes right after "João", the last Gospel loaded; if "João" is gone, it goes last.

The reverse deletes the author-less lesson with this title and closes the gap it leaves.
"""

from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps

from features.sunday_school.late_lesson_load import insert_lessons_after, remove_lessons
from features.sunday_school.lesson_files import LESSON_DATA_DIR

YEAR = 2026
DATA_DIR = LESSON_DATA_DIR / "0005_load_atos"
PRECEDING_TITLE = "João"


def forward(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    insert_lessons_after(apps, YEAR, PRECEDING_TITLE, DATA_DIR)


def backward(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    remove_lessons(apps, YEAR, DATA_DIR)


class Migration(migrations.Migration):
    dependencies = [("sunday_school", "0004_load_joao")]

    operations = [migrations.RunPython(forward, backward)]
