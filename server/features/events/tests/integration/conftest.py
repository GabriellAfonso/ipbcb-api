from collections.abc import Iterator
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import pytest
from dependency_injector import providers
from pytest_django.fixtures import SettingsWrapper

from features.events.domain.event_enums import EventVisibility
from features.events.models.event import Event
from features.events.tests.fakes import FixedClock

if TYPE_CHECKING:
    from config.di import Container

# 2026-11-14 12:00 in São Paulo (UTC-3): "today" for every API test unless a test moves it.
NOON_NOV_14 = datetime(2026, 11, 14, 15, 0, tzinfo=timezone.utc)
TODAY = date(2026, 11, 14)
PUBLIC_URL = "/api/events/"
ADMIN_URL = "/api/admin/events/"


def public_detail_url(event_id: int) -> str:
    return f"{PUBLIC_URL}{event_id}/"


def admin_detail_url(event_id: int) -> str:
    return f"{ADMIN_URL}{event_id}/"


class MakeEvent(Protocol):
    def __call__(
        self,
        start_date: date = ...,
        end_date: date | None = ...,
        start_time: time | None = ...,
        visibility: EventVisibility = ...,
        title: str = ...,
    ) -> Event: ...


@pytest.fixture
def media_root(tmp_path: Path, settings: SettingsWrapper) -> Path:
    """An empty MEDIA_ROOT with production media delivery (X-Accel-Redirect), as in the media
    feature's tests. ``default_storage`` follows the setting change."""
    root = tmp_path / "media"
    root.mkdir()
    settings.MEDIA_ROOT = root
    settings.DEBUG = False
    return root


@pytest.fixture
def clock(di_container: "Container") -> Iterator[FixedClock]:
    """The clock every view reads "today" from, stopped at noon on 2026-11-14 in São Paulo."""
    fixed = FixedClock(NOON_NOV_14)
    with di_container.clock.override(providers.Object(fixed)):
        yield fixed


@pytest.fixture
def make_event(media_root: Path) -> MakeEvent:
    """Insert an event row with a real (tiny) file under ``events/``."""
    counter = iter(range(1, 10_000))

    def _make(
        start_date: date = TODAY,
        end_date: date | None = None,
        start_time: time | None = None,
        visibility: EventVisibility = EventVisibility.PUBLIC,
        title: str = "",
    ) -> Event:
        number = next(counter)
        image_path = f"events/seed-{number}.jpg"
        (media_root / "events").mkdir(exist_ok=True)
        (media_root / image_path).write_bytes(b"\xff\xd8seed")
        return Event.objects.create(
            title=title or f"Evento {number}",
            start_date=start_date,
            end_date=end_date,
            start_time=start_time,
            image_path=image_path,
            visibility=visibility.value,
        )

    return _make
