from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from conftest import make_user
from features.accounts.models.user import User
from features.songs.models import Played, Setlist, Song
from features.songs.repositories.setlist_repository import SetlistRepositoryImpl
from features.songs.setlist_dtos import SetlistItemInput

SP = ZoneInfo("America/Sao_Paulo")
SUNDAY = date(2026, 10, 4)
SAVED_AT = datetime(2026, 10, 1, 19, 0, tzinfo=SP)


def _slot(hour: int, minute: int) -> datetime:
    return datetime(2026, 10, 4, hour, minute, tzinfo=SP)


@pytest.mark.django_db
class TestReplace:
    repository = SetlistRepositoryImpl()

    def setup_method(self) -> None:
        self.author: User = make_user(username="ana")
        self.songs = [Song.objects.create(title=f"S{i}", artist="A") for i in range(3)]

    def _items(self, *indexes: int) -> list[SetlistItemInput]:
        return [
            SetlistItemInput(song_id=self.songs[i].pk, position=pos, tone="G")
            for pos, i in enumerate(indexes, start=1)
        ]

    def test_creates_with_items_in_order(self) -> None:
        setlist, replaced = self.repository.replace(
            SUNDAY, self.author.pk, self._items(2, 0), SAVED_AT
        )
        assert not replaced
        assert [(i.position, i.title) for i in setlist.items] == [(1, "S2"), (2, "S0")]
        assert setlist.saved_by_name == "ana" and setlist.saved_at == SAVED_AT

    def test_replaces_every_item_and_author(self) -> None:
        other = make_user(username="bia")
        self.repository.replace(SUNDAY, self.author.pk, self._items(0, 1), SAVED_AT)
        setlist, replaced = self.repository.replace(SUNDAY, other.pk, self._items(2), SAVED_AT)
        assert replaced
        assert [i.title for i in setlist.items] == ["S2"]
        assert setlist.saved_by_name == "bia"

    def test_resave_keeps_the_reminder_slot(self) -> None:
        self.repository.replace(SUNDAY, self.author.pk, self._items(0), SAVED_AT)
        assert self.repository.claim_reminder_slot(SUNDAY, _slot(21, 0))
        self.repository.replace(SUNDAY, self.author.pk, self._items(1), SAVED_AT)
        assert Setlist.objects.get().last_reminder_slot == _slot(21, 0)

    def test_deleted_author_reads_as_none(self) -> None:
        self.repository.replace(SUNDAY, self.author.pk, self._items(0), SAVED_AT)
        self.author.delete()
        setlist = self.repository.get_by_date(SUNDAY)
        assert setlist is not None and setlist.saved_by_name is None


@pytest.mark.django_db
class TestReminderQueries:
    repository = SetlistRepositoryImpl()

    def setup_method(self) -> None:
        Setlist.objects.create(date=SUNDAY, saved_at=SAVED_AT)

    def test_claim_once_per_slot_and_only_forward(self) -> None:
        assert self.repository.claim_reminder_slot(SUNDAY, _slot(21, 0))
        assert not self.repository.claim_reminder_slot(SUNDAY, _slot(21, 0))
        assert self.repository.claim_reminder_slot(SUNDAY, _slot(21, 30))
        assert not self.repository.claim_reminder_slot(SUNDAY, _slot(21, 0))

    def test_claim_without_setlist_is_false(self) -> None:
        assert not self.repository.claim_reminder_slot(date(2026, 10, 11), _slot(21, 0))

    def test_has_plays_counts_any_row_for_the_date(self) -> None:
        assert not self.repository.has_plays(SUNDAY)
        song = Song.objects.create(title="Other", artist="A")
        Played.objects.create(song=song, tone="D", position=7, date=SUNDAY)
        assert self.repository.has_plays(SUNDAY)
