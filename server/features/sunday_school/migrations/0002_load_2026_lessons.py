"""Load the 2026 Sunday school lessons (specs/026-sunday-school FR-022, research R-08).

Reason: the 18 lessons given in 2026 ("O Drama das Escrituras") existed only as PDFs and slide
decks; they were converted by hand into the frozen JSON files under ``data/2026/`` and reviewed
before commit. A data migration (not a SQL dump) so the load runs on the deploy's ``migrate``,
goes through the same content schema as API writes and depends on no database id. The files
never change once applied; later corrections go through the panel.

All lessons are published, with ``teacher`` empty and no author. Only the dates marked
"oficial" in the source list are set; inferred dates are left out on purpose.

The reverse deletes the lessons of 2026 that have no author and a title from these files, then
the year row if it is left without lessons.
"""

from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps

from features.sunday_school.lesson_files import LESSON_DATA_DIR, read_lessons, read_year

DATA_DIR = LESSON_DATA_DIR / "2026"


def forward(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    year_model = apps.get_model("sunday_school", "SundaySchoolYear")
    lesson_model = apps.get_model("sunday_school", "SundaySchoolLesson")
    year_file = read_year(DATA_DIR)
    year, _ = year_model.objects.get_or_create(
        year=year_file.year, defaults={"theme": year_file.theme}
    )
    first = lesson_model.objects.filter(year=year).count()
    lesson_model.objects.bulk_create(
        lesson_model(
            year=year,
            title=lesson.title,
            date=lesson.date,
            teacher="",
            status="published",
            position=first + index,
            content=lesson.content.model_dump(mode="json"),
        )
        for index, lesson in enumerate(read_lessons(DATA_DIR))
    )


def backward(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    year_model = apps.get_model("sunday_school", "SundaySchoolYear")
    lesson_model = apps.get_model("sunday_school", "SundaySchoolLesson")
    year_file = read_year(DATA_DIR)
    titles = [lesson.title for lesson in read_lessons(DATA_DIR)]
    lesson_model.objects.filter(
        year__year=year_file.year, created_by__isnull=True, title__in=titles
    ).delete()
    year_model.objects.filter(year=year_file.year, lessons__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [("sunday_school", "0001_initial")]

    operations = [migrations.RunPython(forward, backward)]
