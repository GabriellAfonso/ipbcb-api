"""Named test doubles for the hymnal view history feature.

Named classes rather than inline stubs, per CLAUDE.md §10.
"""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from features.songs.hymnal_history_dtos import ServiceWindowDTO
from features.songs.models.song import Song
from features.songs.setlist_dtos import SetlistDTO, SetlistItemDTO, SetlistItemInput
from core.models import ChurchService
from features.songs.models.hymnal_history import (
    HymnalHistorySettings,
    HymnalViewEvent,
)


class FrozenClock:
    """Clock that always returns the same instant, so time-based rules are testable."""

    def __init__(self, moment: datetime) -> None:
        self._moment = moment

    def now(self) -> datetime:
        return self._moment


class FakeHymnalHistoryRepository:
    """In-memory implementation of ``HymnalHistoryRepository``.

    Holds unsaved model instances; nothing here touches the database.
    """

    def __init__(
        self,
        stored_events: list[HymnalViewEvent] | None = None,
        hymn_ids: set[int] | None = None,
        windows: list[ChurchService] | None = None,
        settings: HymnalHistorySettings | None = None,
        hymn_labels: dict[int, tuple[str, str]] | None = None,
    ) -> None:
        self.stored_events = stored_events or []
        self.hymn_ids = hymn_ids or set()
        self.windows = windows or []
        self.settings = settings or HymnalHistorySettings(id=1)
        self.hymn_labels = hymn_labels or {}
        self.created_events: list[HymnalViewEvent] = []
        self.deleted_windows: list[ChurchService] = []

    def get_existing_client_event_ids(self, client_event_ids: list[UUID]) -> set[UUID]:
        wanted = set(client_event_ids)
        return {e.client_event_id for e in self.stored_events if e.client_event_id in wanted}

    def get_collapse_candidates(
        self,
        pairs: set[tuple[int, str]],
        window_start: datetime,
        window_end: datetime,
    ) -> list[tuple[int, str, datetime]]:
        return [
            (e.hymn_id, e.device_id, e.viewed_at)
            for e in self.stored_events
            if (e.hymn_id, e.device_id) in pairs and window_start <= e.viewed_at <= window_end
        ]

    def get_existing_hymn_ids(self, hymn_ids: set[int]) -> set[int]:
        return hymn_ids & self.hymn_ids

    def bulk_create_events(self, events: list[HymnalViewEvent]) -> None:
        self.created_events.extend(events)
        self.stored_events.extend(events)

    def list_events_in_range(
        self,
        start: datetime | None,
        end: datetime | None,
    ) -> list[tuple[int, datetime, str]]:
        rows = []
        for event in self.stored_events:
            if start is not None and event.viewed_at < start:
                continue
            if end is not None and event.viewed_at >= end:
                continue
            rows.append((event.hymn_id, event.viewed_at, event.device_id))
        return rows

    def get_hymn_labels(self, hymn_ids: set[int]) -> dict[int, tuple[str, str]]:
        return {pk: label for pk, label in self.hymn_labels.items() if pk in hymn_ids}

    def list_active_service_windows(self) -> list[ChurchService]:
        return [w for w in self.windows if w.active]

    def list_service_windows(self) -> list[ChurchService]:
        return list(self.windows)

    def get_service_window(self, window_id: int) -> ChurchService | None:
        return next((w for w in self.windows if w.id == window_id), None)

    def create_service_window(self, data: ServiceWindowDTO) -> ChurchService:
        window = ChurchService(
            id=len(self.windows) + 1,
            name=data.name,
            weekday=data.weekday,
            start_time=data.start_time,
            end_time=data.end_time,
            active=data.active,
        )
        self.windows.append(window)
        return window

    def update_service_window(
        self,
        window: ChurchService,
        changes: dict[str, Any],
    ) -> ChurchService:
        for field, value in changes.items():
            setattr(window, field, value)
        return window

    def delete_service_window(self, window: ChurchService) -> None:
        self.windows = [w for w in self.windows if w.id != window.id]
        self.deleted_windows.append(window)

    def get_settings(self) -> HymnalHistorySettings:
        return self.settings

    def update_settings(self, changes: dict[str, int]) -> HymnalHistorySettings:
        for field, value in changes.items():
            setattr(self.settings, field, value)
        return self.settings


class FakeSetlistRepository:
    """In-memory ``SetlistRepository``. Songs are named from ``titles`` (song id -> title);
    ``played_dates`` stands for dates with ``Played`` rows.

    >>> FakeSetlistRepository().current(date(2026, 10, 1)) is None
    True
    """

    def __init__(self, titles: dict[int, str] | None = None) -> None:
        self.titles = dict(titles or {})
        self.setlists: dict[date, SetlistDTO] = {}
        self.slots: dict[date, datetime] = {}
        self.played_dates: set[date] = set()
        self.replace_calls = 0

    def replace(
        self, day: date, author_id: UUID, items: list[SetlistItemInput], saved_at: datetime
    ) -> tuple[SetlistDTO, bool]:
        self.replace_calls += 1
        existed = day in self.setlists
        self.setlists[day] = SetlistDTO(
            date=day,
            items=[self._item(item) for item in sorted(items, key=lambda i: i.position)],
            saved_by_name=str(author_id),
            saved_at=saved_at,
        )
        return self.setlists[day], existed

    def delete(self, day: date) -> bool:
        return self.setlists.pop(day, None) is not None

    def get_by_date(self, day: date) -> SetlistDTO | None:
        return self.setlists.get(day)

    def current(self, today: date) -> SetlistDTO | None:
        upcoming = sorted(day for day in self.setlists if day >= today)
        return self.setlists[upcoming[0]] if upcoming else None

    def pending(self, today: date) -> list[SetlistDTO]:
        days = [d for d in self.setlists if d <= today and d not in self.played_dates]
        return [self.setlists[d] for d in sorted(days, reverse=True)]

    def has_plays(self, day: date) -> bool:
        return day in self.played_dates

    def claim_reminder_slot(self, day: date, slot: datetime) -> bool:
        if day not in self.setlists:
            return False
        last = self.slots.get(day)
        if last is not None and last >= slot:
            return False
        self.slots[day] = slot
        return True

    def _item(self, item: SetlistItemInput) -> SetlistItemDTO:
        title = self.titles.get(item.song_id, f"Song {item.song_id}")
        return SetlistItemDTO(
            position=item.position, song_id=item.song_id, title=title, artist="A", tone=item.tone
        )


class FakeSongLookup:
    """``SongLookup`` over a fixed set of existing song ids."""

    def __init__(self, existing_ids: set[int]) -> None:
        self.existing_ids = set(existing_ids)

    def get_songs_in_bulk(self, ids: set[int]) -> dict[int, Song]:
        return {i: Song(id=i, title=f"Song {i}", artist="A") for i in ids & self.existing_ids}
