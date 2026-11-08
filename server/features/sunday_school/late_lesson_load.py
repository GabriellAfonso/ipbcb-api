"""Shared steps of the migrations that add a lesson after a year's load already ran in production
(specs/026-sunday-school FR-022, research R-08 "Later lessons").

Each such migration owns a folder under ``migrations/data/`` that no other migration reads, and
names the lesson its own lessons follow. Called with the migration's historical app registry.
"""

from pathlib import Path

from django.db.migrations.state import StateApps
from django.db.models import F, Max, Model, QuerySet

from features.sunday_school.lesson_files import read_lessons


def insert_lessons_after(apps: StateApps, year: int, preceding_title: str, directory: Path) -> None:
    """Insert ``directory``'s lessons right after ``preceding_title``, shifting later ones down.

    >>> insert_lessons_after(apps, 2026, "Daniel", LESSON_DATA_DIR / "0003_load_oseias_joel_amos")
    """
    year_row = apps.get_model("sunday_school", "SundaySchoolYear").objects.get(year=year)
    lesson_model = apps.get_model("sunday_school", "SundaySchoolLesson")
    lessons = read_lessons(directory)
    position = _position_after(lesson_model.objects.filter(year=year_row), preceding_title)
    lesson_model.objects.filter(year=year_row, position__gte=position).update(
        position=F("position") + len(lessons)
    )
    for offset, lesson in enumerate(lessons):
        lesson_model.objects.create(
            year=year_row,
            title=lesson.title,
            date=lesson.date,
            teacher=lesson.teacher,
            status="published",
            position=position + offset,
            content=lesson.content.model_dump(mode="json"),
        )


def remove_lessons(apps: StateApps, year: int, directory: Path) -> None:
    """Reverse of ``insert_lessons_after``: delete each author-less lesson and close its gap.

    >>> remove_lessons(apps, 2026, LESSON_DATA_DIR / "0003_load_oseias_joel_amos")
    """
    lesson_model = apps.get_model("sunday_school", "SundaySchoolLesson")
    for lesson in read_lessons(directory):
        added = lesson_model.objects.filter(
            year__year=year, created_by__isnull=True, title=lesson.title
        ).first()
        if added is None:
            continue
        added.delete()
        lesson_model.objects.filter(year_id=added.year_id, position__gt=added.position).update(
            position=F("position") - 1
        )


def replace_lessons_content(apps: StateApps, year: int, directory: Path) -> None:
    """Give each author-less lesson titled as a file in ``directory`` that file's content.

    Touches nothing else on the row, and skips a lesson that no longer exists.

    >>> replace_lessons_content(apps, 2026, LESSON_DATA_DIR / "0006_replace_atos_content")
    """
    lesson_model = apps.get_model("sunday_school", "SundaySchoolLesson")
    for lesson in read_lessons(directory):
        loaded = lesson_model.objects.filter(
            year__year=year, created_by__isnull=True, title=lesson.title
        ).first()
        if loaded is None:
            continue
        loaded.content = lesson.content.model_dump(mode="json")
        # save, not a queryset update: updated_at has to record the change.
        loaded.save(update_fields=["content", "updated_at"])


def _position_after(lessons: QuerySet[Model], preceding_title: str) -> int:
    """The position right after ``preceding_title`` in ``lessons`` (one year), or the end."""
    preceding = (
        lessons.filter(title=preceding_title, created_by__isnull=True)
        .values_list("position", flat=True)
        .first()
    )
    if preceding is not None:
        return int(preceding) + 1
    # Max, not count: positions may have gaps after deletes (research R-07).
    last = lessons.aggregate(last=Max("position"))["last"]
    return 0 if last is None else int(last) + 1
