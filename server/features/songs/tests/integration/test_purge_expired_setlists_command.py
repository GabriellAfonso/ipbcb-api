from datetime import datetime
from io import StringIO
from zoneinfo import ZoneInfo

import pytest
from dependency_injector import providers
from django.core.management import call_command

from config.di import Container
from features.songs.models import Setlist
from features.songs.tests.fakes import FrozenClock

SP = ZoneInfo("America/Sao_Paulo")


@pytest.mark.django_db
def test_deletes_expired_and_prints_the_count(di_container: Container) -> None:
    saved_at = datetime(2026, 1, 1, tzinfo=SP)
    for day in ("2026-01-04", "2026-09-27"):
        Setlist.objects.create(date=day, saved_at=saved_at)
    out = StringIO()
    with di_container.clock.override(
        providers.Object(FrozenClock(datetime(2026, 10, 6, tzinfo=SP)))
    ):
        call_command("purge_expired_setlists", stdout=out)
    assert out.getvalue().strip() == "purged 1 setlists"
    assert list(Setlist.objects.values_list("date", flat=True)) == [datetime(2026, 9, 27).date()]
