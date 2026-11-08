"""Replace the content of the "Atos" lesson with the lesson actually given (specs/026-sunday-school
FR-022, research R-08).

Reason: ``0005_load_atos`` loaded the PDF outline ("Roteiro Ato 5"), not the lesson given on
2026-11-08 ("O Drama das Escrituras Ato 5.pdf"), and it already reached production, so it cannot be
edited. Only the content changes; title, date, teacher, status and position stay. If the lesson was
deleted, nothing happens.

The reverse puts back the outline content that ``0005`` loaded.
"""

from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps

from features.sunday_school.late_lesson_load import replace_lessons_content
from features.sunday_school.lesson_files import LESSON_DATA_DIR

YEAR = 2026
DATA_DIR = LESSON_DATA_DIR / "0006_replace_atos_content"
OUTLINE_DATA_DIR = LESSON_DATA_DIR / "0005_load_atos"


def forward(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    replace_lessons_content(apps, YEAR, DATA_DIR)


def backward(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    replace_lessons_content(apps, YEAR, OUTLINE_DATA_DIR)


class Migration(migrations.Migration):
    dependencies = [("sunday_school", "0005_load_atos")]

    operations = [migrations.RunPython(forward, backward)]
