"""The 2026 load migrations, forward and back (specs/026-sunday-school US5).

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
add_hosea = import_module("features.sunday_school.migrations.0003_load_oseias_joel_amos")
add_john = import_module("features.sunday_school.migrations.0004_load_joao")
# Later lessons, in migration order; reversed newest first.
LATE_LOADS = [add_hosea, add_john]

pytestmark = pytest.mark.django_db


def test_fresh_database_holds_the_2026_lessons() -> None:
    lessons = list(SundaySchoolLesson.objects.filter(year__year=2026).order_by("position"))

    assert SundaySchoolYear.objects.get(year=2026).theme == "O Drama das Escrituras"
    assert [lesson.position for lesson in lessons] == list(range(20))
    assert {lesson.status for lesson in lessons} == {"published"}
    assert sum(lesson.date is not None for lesson in lessons) == 10
    assert lessons[10].date == datetime.date(2026, 8, 16)
    assert [lesson.title for lesson in lessons[10:13]] == [
        "Daniel",
        "Oseias, Joel e Amós",
        "Obadias, Jonas e Miqueias",
    ]
    assert [lesson.title for lesson in lessons[-2:]] == ["Marcos", "João"]
    assert (lessons[-1].date, lessons[-1].teacher) == (datetime.date(2026, 11, 1), "Jean Monjardim")
    assert {lesson.teacher for lesson in lessons[:-1]} == {""}
    assert all(lesson.created_by_id is None for lesson in lessons)


def test_reverse_removes_only_what_it_created() -> None:
    kept = SundaySchoolLesson.objects.create(
        year=SundaySchoolYear.objects.get(year=2026),
        title="Panorama de Gênesis",
        status="draft",
        position=20,
        content={"sections": []},
        created_by=make_user("lider"),
    )

    _reverse_late_loads()
    load.backward(apps, None)

    assert list(SundaySchoolLesson.objects.values_list("pk", flat=True)) == [kept.pk]
    assert SundaySchoolYear.objects.filter(year=2026).exists()


def test_reverse_then_forward_restores_the_load() -> None:
    _reverse_late_loads()
    load.backward(apps, None)
    assert not SundaySchoolYear.objects.exists()

    load.forward(apps, None)
    for late in LATE_LOADS:
        late.forward(apps, None)

    assert SundaySchoolLesson.objects.count() == 20


def _reverse_late_loads() -> None:
    for late in reversed(LATE_LOADS):
        late.backward(apps, None)


def _titles_in_order() -> list[str]:
    return list(SundaySchoolLesson.objects.order_by("position").values_list("title", flat=True))


def test_hosea_reverse_closes_the_gap() -> None:
    add_hosea.backward(apps, None)

    positions = list(
        SundaySchoolLesson.objects.order_by("position").values_list("position", flat=True)
    )
    assert positions == list(range(19))
    assert "Oseias, Joel e Amós" not in _titles_in_order()


def test_hosea_goes_last_when_daniel_is_gone() -> None:
    add_hosea.backward(apps, None)
    SundaySchoolLesson.objects.filter(title="Daniel").delete()

    add_hosea.forward(apps, None)

    assert _titles_in_order()[-1] == "Oseias, Joel e Amós"


def test_john_reverse_removes_only_john() -> None:
    add_john.backward(apps, None)

    assert _titles_in_order()[-1] == "Marcos"
    assert SundaySchoolLesson.objects.count() == 19
