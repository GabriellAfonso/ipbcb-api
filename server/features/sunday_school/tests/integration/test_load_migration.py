"""The 2026 initial-load migration, forward and back (specs/026-sunday-school US5).

The test database is built by running every migration, so the forward step already ran; the
functions are called again here with the live app registry to check the reverse and a re-run.
"""

import datetime
from importlib import import_module

import pytest
from django.apps import apps

from conftest import make_user
from features.sunday_school.models import SundaySchoolLesson, SundaySchoolYear

load = import_module("features.sunday_school.migrations.0002_load_2026_lessons")

pytestmark = pytest.mark.django_db


def test_fresh_database_holds_the_2026_lessons() -> None:
    lessons = list(SundaySchoolLesson.objects.filter(year__year=2026).order_by("position"))

    assert SundaySchoolYear.objects.get(year=2026).theme == "O Drama das Escrituras"
    assert [lesson.position for lesson in lessons] == list(range(18))
    assert {lesson.status for lesson in lessons} == {"published"}
    assert sum(lesson.date is not None for lesson in lessons) == 9
    assert lessons[10].date == datetime.date(2026, 8, 16)
    assert {lesson.teacher for lesson in lessons} == {""}
    assert all(lesson.created_by_id is None for lesson in lessons)


def test_reverse_removes_only_what_it_created() -> None:
    kept = SundaySchoolLesson.objects.create(
        year=SundaySchoolYear.objects.get(year=2026),
        title="Panorama de Gênesis",
        status="draft",
        position=18,
        content={"sections": []},
        created_by=make_user("lider"),
    )

    load.backward(apps, None)

    assert list(SundaySchoolLesson.objects.values_list("pk", flat=True)) == [kept.pk]
    assert SundaySchoolYear.objects.filter(year=2026).exists()


def test_reverse_then_forward_restores_the_load() -> None:
    load.backward(apps, None)
    assert not SundaySchoolYear.objects.exists()

    load.forward(apps, None)

    assert SundaySchoolLesson.objects.count() == 18
