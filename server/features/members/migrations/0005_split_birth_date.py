"""Copy each member's single birth date into birth_day, birth_month and birth_year.

Why: ``birth_date`` could not hold a partly known date. The secretary stored "birthday known,
year unknown" as year 0001, a convention written down nowhere, and "year known, birthday
unknown" could not be stored at all without inventing a birthday that then showed up in the
birthdays list (specs/011-split-birth-date/spec.md).

What: day and month are copied as they are; the year is copied unless it is 1, the
placeholder, which becomes an empty year. Members without a birth date keep three empty parts.
One UPDATE for the whole table, through the historical model.

Irreversible on purpose (spec FR-015): once 0006 drops ``birth_date`` a reverse step would
have nothing to write into, and a silent no-op would leave members without birth data.
Recovery is restoring the production dump taken before the deploy.

Verified against a restored production dump before the deploy (quickstart §2): not yet run.
"""

from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.models import Case, Value, When
from django.db.models.functions import ExtractDay, ExtractMonth, ExtractYear

PLACEHOLDER_YEAR = 1


def split_birth_date(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    member_model = apps.get_model("members", "Member")
    member_model.objects.filter(birth_date__isnull=False).update(
        birth_day=ExtractDay("birth_date"),
        birth_month=ExtractMonth("birth_date"),
        birth_year=Case(
            When(birth_date__year=PLACEHOLDER_YEAR, then=Value(None)),
            default=ExtractYear("birth_date"),
        ),
    )


class Migration(migrations.Migration):
    dependencies = [
        ("members", "0004_member_birth_parts"),
    ]

    operations = [
        migrations.RunPython(split_birth_date),
    ]
