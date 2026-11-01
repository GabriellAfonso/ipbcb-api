"""Add the 2026 lesson on João (specs/026-sunday-school FR-022, research R-08).

Reason: this lesson was given on 2026-11-01, after ``0002_load_2026_lessons`` ran in production,
and converted from its slide deck. It lives in its own folder, ``data/0004_load_joao/``. Unlike
the load files it carries the date and the teacher (Jean Monjardim), both given by the user as
official. Published, no author.

It goes right after "Marcos", the last Gospel loaded; if "Marcos" is gone, it goes last.

The reverse deletes the author-less lesson with this title and closes the gap it leaves.
"""

from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps

from features.sunday_school.late_lesson_load import insert_lessons_after, remove_lessons
from features.sunday_school.lesson_files import LESSON_DATA_DIR

YEAR = 2026
DATA_DIR = LESSON_DATA_DIR / "0004_load_joao"
PRECEDING_TITLE = "Marcos"


def forward(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    insert_lessons_after(apps, YEAR, PRECEDING_TITLE, DATA_DIR)


def backward(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    remove_lessons(apps, YEAR, DATA_DIR)


class Migration(migrations.Migration):
    dependencies = [("sunday_school", "0003_load_oseias_joel_amos")]

    operations = [migrations.RunPython(forward, backward)]
