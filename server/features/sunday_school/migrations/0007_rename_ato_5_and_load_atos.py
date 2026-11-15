"""Retitle the Act 5 opening lesson and add the 2026 lesson on the book of Atos
(specs/026-sunday-school FR-022, research R-08).

Reason: the lesson loaded as "Atos" by ``0005`` and ``0006`` (given on 2026-11-08) is the opening
of Act 5 of the drama, not the panorama of the book; the book lesson is a separate one, converted
from "Panorama de Atos dos Apóstolos". Both earlier migrations already reached production, so they
cannot be edited. The Act 5 lesson becomes "A Missão da Igreja" (Act 5 is "spreading the news of
the King: the mission of the church"), keeping its content, date, teacher, status and position.
The book lesson takes the title "Atos", lives in ``data/0007_rename_ato_5_and_load_atos/``, has no
date or teacher yet, is published with no author, and goes right after "A Missão da Igreja"
(last, if that lesson is gone).

The reverse deletes the author-less "Atos" book lesson, closes its gap, and gives the Act 5 lesson
its old title back.
"""

from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps

from features.sunday_school.late_lesson_load import (
    insert_lessons_after,
    remove_lessons,
    rename_lesson,
)
from features.sunday_school.lesson_files import LESSON_DATA_DIR

YEAR = 2026
DATA_DIR = LESSON_DATA_DIR / "0007_rename_ato_5_and_load_atos"
OLD_ACT_5_TITLE = "Atos"
ACT_5_TITLE = "A Missão da Igreja"


def forward(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    rename_lesson(apps, YEAR, OLD_ACT_5_TITLE, ACT_5_TITLE)
    insert_lessons_after(apps, YEAR, ACT_5_TITLE, DATA_DIR)


def backward(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    remove_lessons(apps, YEAR, DATA_DIR)
    rename_lesson(apps, YEAR, ACT_5_TITLE, OLD_ACT_5_TITLE)


class Migration(migrations.Migration):
    dependencies = [("sunday_school", "0006_replace_atos_content")]

    operations = [migrations.RunPython(forward, backward)]
