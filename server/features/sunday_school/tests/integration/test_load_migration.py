"""The 2026 load migrations, forward and back (specs/026-sunday-school US5).

The test database is built by running every migration, so the forward step already ran; the
functions are called again here with the live app registry to check the reverse and a re-run.
"""

import datetime
from importlib import import_module
from pathlib import Path

import pytest
from django.apps import apps

from conftest import make_user
from features.sunday_school.lesson_files import read_lessons
from features.sunday_school.models import SundaySchoolLesson, SundaySchoolYear

load = import_module("features.sunday_school.migrations.0002_load_2026_lessons")
add_hosea = import_module("features.sunday_school.migrations.0003_load_oseias_joel_amos")
add_john = import_module("features.sunday_school.migrations.0004_load_joao")
add_acts = import_module("features.sunday_school.migrations.0005_load_atos")
replace_acts = import_module("features.sunday_school.migrations.0006_replace_atos_content")
add_acts_book = import_module("features.sunday_school.migrations.0007_rename_ato_5_and_load_atos")
# Later lessons, in migration order; reversed newest first.
LATE_LOADS = [add_hosea, add_john, add_acts, replace_acts, add_acts_book]
ACT_5 = add_acts_book.ACT_5_TITLE

pytestmark = pytest.mark.django_db


@pytest.fixture
def before_acts_book() -> None:
    """The state 0005 and 0006 ran against: the Act 5 lesson still titled "Atos", no book lesson."""
    add_acts_book.backward(apps, None)


def test_fresh_database_holds_the_2026_lessons() -> None:
    lessons = list(SundaySchoolLesson.objects.filter(year__year=2026).order_by("position"))

    assert SundaySchoolYear.objects.get(year=2026).theme == "O Drama das Escrituras"
    assert [lesson.position for lesson in lessons] == list(range(22))
    assert {lesson.status for lesson in lessons} == {"published"}
    assert sum(lesson.date is not None for lesson in lessons) == 11
    assert lessons[10].date == datetime.date(2026, 8, 16)
    assert [lesson.title for lesson in lessons[10:13]] == [
        "Daniel",
        "Oseias, Joel e Amós",
        "Obadias, Jonas e Miqueias",
    ]
    assert [lesson.title for lesson in lessons[-4:]] == ["Marcos", "João", ACT_5, "Atos"]
    assert (lessons[-3].date, lessons[-3].teacher) == (datetime.date(2026, 11, 1), "Jean Monjardim")
    assert (lessons[-2].date, lessons[-2].teacher) == (datetime.date(2026, 11, 8), "")
    assert (lessons[-1].date, lessons[-1].teacher) == (None, "")
    assert {lesson.teacher for lesson in lessons if lesson.title != "João"} == {""}
    assert all(lesson.created_by_id is None for lesson in lessons)


def test_reverse_removes_only_what_it_created() -> None:
    kept = SundaySchoolLesson.objects.create(
        year=SundaySchoolYear.objects.get(year=2026),
        title="Panorama de Gênesis",
        status="draft",
        position=22,
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

    assert SundaySchoolLesson.objects.count() == 22


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
    assert positions == list(range(21))
    assert "Oseias, Joel e Amós" not in _titles_in_order()


def test_hosea_goes_last_when_daniel_is_gone() -> None:
    add_hosea.backward(apps, None)
    SundaySchoolLesson.objects.filter(title="Daniel").delete()

    add_hosea.forward(apps, None)

    assert _titles_in_order()[-1] == "Oseias, Joel e Amós"


def test_john_reverse_removes_only_john() -> None:
    add_john.backward(apps, None)

    assert _titles_in_order()[-3:] == ["Marcos", ACT_5, "Atos"]
    assert SundaySchoolLesson.objects.count() == 21


@pytest.mark.usefixtures("before_acts_book")
def test_acts_reverse_removes_only_acts() -> None:
    add_acts.backward(apps, None)

    assert _titles_in_order()[-1] == "João"
    assert SundaySchoolLesson.objects.count() == 20


@pytest.mark.usefixtures("before_acts_book")
def test_acts_goes_last_when_john_is_gone() -> None:
    add_acts.backward(apps, None)
    SundaySchoolLesson.objects.filter(title="João").delete()

    add_acts.forward(apps, None)

    assert _titles_in_order()[-1] == "Atos"


def _content_of_folder(directory: Path) -> dict[str, object]:
    return read_lessons(directory)[0].content.model_dump(mode="json")


def test_fresh_database_holds_the_acts_lesson_given() -> None:
    act_5 = SundaySchoolLesson.objects.get(title=ACT_5)

    assert act_5.content == _content_of_folder(replace_acts.DATA_DIR)
    assert act_5.content != _content_of_folder(replace_acts.OUTLINE_DATA_DIR)


@pytest.mark.usefixtures("before_acts_book")
def test_acts_replacement_reverse_restores_the_outline_and_keeps_the_row() -> None:
    SundaySchoolLesson.objects.filter(title="Atos").update(teacher="Professor")
    before = SundaySchoolLesson.objects.get(title="Atos")

    replace_acts.backward(apps, None)

    after = SundaySchoolLesson.objects.get(title="Atos")
    assert after.content == _content_of_folder(replace_acts.OUTLINE_DATA_DIR)
    assert (after.pk, after.date, after.teacher, after.status, after.position) == (
        before.pk,
        before.date,
        "Professor",
        before.status,
        before.position,
    )


@pytest.mark.usefixtures("before_acts_book")
def test_acts_replacement_records_the_change_time() -> None:
    long_ago = datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc)
    SundaySchoolLesson.objects.filter(title="Atos").update(updated_at=long_ago)

    replace_acts.forward(apps, None)

    assert SundaySchoolLesson.objects.get(title="Atos").updated_at > long_ago


@pytest.mark.usefixtures("before_acts_book")
def test_acts_replacement_skips_a_deleted_lesson() -> None:
    add_acts.backward(apps, None)

    replace_acts.forward(apps, None)

    assert "Atos" not in _titles_in_order()


@pytest.mark.usefixtures("before_acts_book")
def test_acts_replacement_leaves_a_lesson_written_in_the_panel_alone() -> None:
    add_acts.backward(apps, None)
    written = SundaySchoolLesson.objects.create(
        year=SundaySchoolYear.objects.get(year=2026),
        title="Atos",
        status="draft",
        position=20,
        content={"sections": []},
        created_by=make_user("lider"),
    )

    replace_acts.forward(apps, None)

    written.refresh_from_db()
    assert written.content == {"sections": []}


def test_fresh_database_holds_the_acts_book_lesson() -> None:
    book = SundaySchoolLesson.objects.get(title="Atos")

    assert book.content == _content_of_folder(add_acts_book.DATA_DIR)
    assert book.position == SundaySchoolLesson.objects.get(title=ACT_5).position + 1


def test_acts_book_reverse_restores_the_act_5_title_and_keeps_the_row() -> None:
    before = SundaySchoolLesson.objects.get(title=ACT_5)

    add_acts_book.backward(apps, None)

    after = SundaySchoolLesson.objects.get(title="Atos")
    assert (after.pk, after.content, after.position) == (before.pk, before.content, before.position)
    assert _titles_in_order()[-1] == "Atos"
    assert SundaySchoolLesson.objects.count() == 21


def test_acts_book_rename_records_the_change_time() -> None:
    add_acts_book.backward(apps, None)
    long_ago = datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc)
    SundaySchoolLesson.objects.filter(title="Atos").update(updated_at=long_ago)

    add_acts_book.forward(apps, None)

    assert SundaySchoolLesson.objects.get(title=ACT_5).updated_at > long_ago


def test_acts_book_goes_last_when_the_act_5_lesson_is_gone() -> None:
    add_acts_book.backward(apps, None)
    SundaySchoolLesson.objects.filter(title="Atos").delete()

    add_acts_book.forward(apps, None)

    assert _titles_in_order()[-2:] == ["João", "Atos"]
    assert ACT_5 not in _titles_in_order()


def test_acts_book_rename_leaves_a_lesson_written_in_the_panel_alone() -> None:
    add_acts_book.backward(apps, None)
    SundaySchoolLesson.objects.filter(title="Atos").delete()
    written = SundaySchoolLesson.objects.create(
        year=SundaySchoolYear.objects.get(year=2026),
        title="Atos",
        status="draft",
        position=20,
        content={"sections": []},
        created_by=make_user("lider"),
    )

    add_acts_book.forward(apps, None)

    written.refresh_from_db()
    assert written.title == "Atos"
