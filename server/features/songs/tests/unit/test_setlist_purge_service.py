from datetime import date, datetime, timezone

import pytest

from features.songs.services.setlist_purge_service import SetlistPurgeService
from features.songs.setlist_dtos import SetlistDTO
from features.songs.tests.fakes import FakeSetlistRepository, FrozenClock

# 2026-10-01 01:00 UTC is still 2026-09-30 in Sao Paulo: cutoffs come from the local date.
NOW = datetime(2026, 10, 1, 1, 0, tzinfo=timezone.utc)


def _with_setlists(*days: date) -> FakeSetlistRepository:
    repository = FakeSetlistRepository()
    for day in days:
        repository.setlists[day] = SetlistDTO(date=day, items=[], saved_by_name=None, saved_at=NOW)
    return repository


def test_purges_confirmed_after_30_and_unconfirmed_after_90_days() -> None:
    repository = _with_setlists(
        date(2026, 8, 30), date(2026, 8, 31), date(2026, 7, 1), date(2026, 7, 2)
    )
    repository.played_dates |= {date(2026, 8, 30), date(2026, 8, 31)}
    deleted = SetlistPurgeService(repository, FrozenClock(NOW)).purge_expired()
    assert deleted == 2
    assert sorted(repository.setlists) == [date(2026, 7, 2), date(2026, 8, 31)]


def test_logs_count_and_cutoffs(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("INFO"):
        SetlistPurgeService(_with_setlists(), FrozenClock(NOW)).purge_expired()
    [record] = [r for r in caplog.records if r.getMessage() == "setlist_purged"]
    fields = vars(record)
    assert fields["deleted"] == 0
    assert fields["confirmed_before"] == "2026-08-31"
    assert fields["unconfirmed_before"] == "2026-07-02"
