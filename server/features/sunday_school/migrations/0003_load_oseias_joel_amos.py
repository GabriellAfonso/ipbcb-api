"""Add the 2026 lesson on Oseias, Joel and Amós (specs/026-sunday-school FR-022, research R-08).

Reason: this lesson was missing from the PDFs converted for ``0002_load_2026_lessons`` and arrived
later. ``0002`` already ran in production on 2026-10-29, so its frozen files cannot grow: this
lesson lives in its own folder, ``data/0003_load_oseias_joel_amos/``, which no other migration
reads. Same rules as ``0002``: published, ``teacher`` empty, no author, no date (the source marks
none as official).

It goes right after "Daniel", where it falls in Bible order (before "Obadias, Jonas e
Miqueias"); every later lesson of 2026 moves one position down. If "Daniel" is gone, it goes last.

The reverse deletes the author-less lesson with this title and closes the gap it leaves.
"""

from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps

from features.sunday_school.late_lesson_load import insert_lessons_after, remove_lessons
from features.sunday_school.lesson_files import LESSON_DATA_DIR

YEAR = 2026
DATA_DIR = LESSON_DATA_DIR / "0003_load_oseias_joel_amos"
PRECEDING_TITLE = "Daniel"


def forward(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    insert_lessons_after(apps, YEAR, PRECEDING_TITLE, DATA_DIR)


def backward(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    remove_lessons(apps, YEAR, DATA_DIR)


class Migration(migrations.Migration):
    dependencies = [("sunday_school", "0002_load_2026_lessons")]

    operations = [migrations.RunPython(forward, backward)]
