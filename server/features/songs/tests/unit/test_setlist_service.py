from datetime import date, datetime, timezone
from uuid import UUID, uuid4

import pytest

from core.application.access_service import AccessService
from core.application.push_service import PushService
from core.application.worship_access_service import WorshipAccessService
from core.domain.exceptions import (
    DuplicateSetlistPositionError,
    NotWorshipMemberError,
    SetlistDateNotSundayError,
    SetlistNotFoundError,
    SongsNotFoundError,
)
from core.domain.push import PushMessageType
from core.tests.fakes import (
    FakeDeviceTokenRepository,
    FakePushSender,
    FakeRoleGrantRepository,
    FakeWorshipMembership,
)
from features.songs.services.setlist_service import SetlistService
from features.songs.setlist_dtos import SetlistDTO, SetlistItemInput
from features.songs.tests.fakes import FakeSetlistRepository, FakeSongLookup, FrozenClock

LEADER, BAND, OUTSIDER = uuid4(), uuid4(), uuid4()
SUNDAY = date(2026, 10, 4)
# Thursday 2026-10-01, noon in Sao Paulo (15:00 UTC).
NOW = datetime(2026, 10, 1, 15, 0, tzinfo=timezone.utc)


class _World:
    """A SetlistService over fakes: LEADER and BAND are worship members, each with one phone;
    OUTSIDER has a phone too but is not in the ministry."""

    def __init__(self, sender: FakePushSender | None = None) -> None:
        self.setlists = FakeSetlistRepository()
        self.sender = sender or FakePushSender()
        tokens = FakeDeviceTokenRepository(
            {"leader-phone": LEADER, "band-phone": BAND, "outsider-phone": OUTSIDER}
        )
        worship = WorshipAccessService(
            FakeWorshipMembership({LEADER, BAND}), AccessService(FakeRoleGrantRepository([], []))
        )
        self.service = SetlistService(
            self.setlists,
            FakeSongLookup({1, 2, 3}),
            worship,
            PushService(tokens, self.sender),
            FrozenClock(NOW),
        )


def _items(*pairs: tuple[int, int]) -> list[SetlistItemInput]:
    return [SetlistItemInput(song_id=song, position=pos, tone="G") for song, pos in pairs]


def _save(world: _World, user: UUID = LEADER, day: date = SUNDAY) -> SetlistDTO:
    return world.service.save(user, day, _items((1, 1), (2, 2)))


class TestSave:
    def test_outsider_is_refused_before_any_write(self) -> None:
        world = _World()
        with pytest.raises(NotWorshipMemberError):
            _save(world, user=OUTSIDER)
        assert world.setlists.replace_calls == 0

    def test_not_sunday(self) -> None:
        world = _World()
        with pytest.raises(SetlistDateNotSundayError):
            _save(world, day=date(2026, 10, 5))
        assert world.setlists.replace_calls == 0

    def test_duplicate_positions(self) -> None:
        world = _World()
        with pytest.raises(DuplicateSetlistPositionError):
            world.service.save(LEADER, SUNDAY, _items((1, 1), (2, 1)))

    def test_missing_songs_are_listed_and_nothing_written(self) -> None:
        world = _World()
        with pytest.raises(SongsNotFoundError) as error:
            world.service.save(LEADER, SUNDAY, _items((1, 1), (9, 2), (7, 3)))
        assert error.value.missing_ids == [7, 9]
        assert world.setlists.replace_calls == 0

    def test_success_uses_the_clock_and_orders_items(self) -> None:
        setlist = _World().service.save(LEADER, SUNDAY, _items((2, 2), (1, 1)))
        assert setlist.saved_at == NOW
        assert [item.position for item in setlist.items] == [1, 2]


class TestSavePush:
    def test_pushes_to_every_worship_member_device(self) -> None:
        world = _World()
        _save(world)
        [(tokens, message)] = world.sender.calls
        assert sorted(tokens) == ["band-phone", "leader-phone"]
        assert message.type is PushMessageType.SETLIST_SAVED and message.date == SUNDAY

    def test_resave_pushes_again(self) -> None:
        world = _World()
        _save(world)
        _save(world)
        assert len(world.sender.calls) == 2

    def test_push_failure_still_returns_the_setlist(self) -> None:
        world = _World(FakePushSender(raises=ConnectionError("down")))
        assert _save(world).date == SUNDAY
        assert world.setlists.get_by_date(SUNDAY) is not None


class TestReads:
    def test_current_is_the_next_sunday_from_local_today(self) -> None:
        world = _World()
        for day in (date(2026, 9, 27), SUNDAY, date(2026, 10, 11)):
            _save(world, day=day)
        current = world.service.current()
        assert current is not None and current.date == SUNDAY

    def test_current_is_none_without_upcoming(self) -> None:
        world = _World()
        _save(world, day=date(2026, 9, 27))
        assert world.service.current() is None

    def test_by_date_missing_raises(self) -> None:
        with pytest.raises(SetlistNotFoundError):
            _World().service.by_date(SUNDAY)

    def test_pending_uses_local_today(self) -> None:
        world = _World()
        for day in (date(2026, 9, 20), date(2026, 9, 27), SUNDAY):
            _save(world, day=day)
        world.setlists.played_dates.add(date(2026, 9, 20))
        assert [s.date for s in world.service.pending()] == [date(2026, 9, 27)]
