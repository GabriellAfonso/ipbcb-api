"""Named test doubles for the hymnal view history feature.

Named classes rather than inline stubs, per CLAUDE.md §10.
"""

from collections.abc import Sequence
from datetime import date, datetime
from typing import Any
from uuid import UUID

from django.db.models import QuerySet

from features.songs.dtos import NewSongInput, SongChangesInput, SongUsage
from features.songs.hymnal_history_dtos import ServiceWindowDTO
from features.songs.models.chord_chart import ChordChart
from features.songs.models.lyrics import Lyrics
from features.songs.models.song import Played, Song
from features.songs.repositories.song_repository import SongRepositoryImpl
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

    def purge(self, confirmed_before: date, unconfirmed_before: date) -> int:
        expired = [
            day
            for day in self.setlists
            if day < (confirmed_before if day in self.played_dates else unconfirmed_before)
        ]
        for day in expired:
            del self.setlists[day]
        return len(expired)

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


class BlindUsageSongRepository(SongRepositoryImpl):
    """Real repository whose first usage read sees nothing: a play saved right after the
    service's check. Later reads (the repository's own re-check) see the database.
    """

    def __init__(self) -> None:
        self._first_read = True

    def get_song_usage(self, song_id: int) -> SongUsage:
        if self._first_read:
            self._first_read = False
            return SongUsage(plays=0, setlist_dates=[])
        return super().get_song_usage(song_id)


class RecordingSongPicker:
    """``SongPicker`` that records every candidate list it is offered.

    Picks the first candidate unless ``choose`` (song id) is among them, so a test controls
    the draw without randomness.

    >>> RecordingSongPicker(choose=7)([3, 7])
    7
    """

    def __init__(self, choose: int | None = None) -> None:
        self.choose = choose
        self.offers: list[list[int]] = []

    def __call__(self, candidates: Sequence[int]) -> int:
        self.offers.append(list(candidates))
        if self.choose is not None and self.choose in candidates:
            return self.choose
        return candidates[0]


def _unused(name: str) -> NotImplementedError:
    return NotImplementedError(f"FakeSongRepository.{name} is not used by these tests")


class FakeSongRepository:
    """In-memory ``SongRepository`` over unsaved ``Song`` instances, keyed by id.

    It spells out the whole protocol because mypy checks the tests against it; the
    methods the catalogue tests never reach raise. ``calls`` records the catalogue
    methods, so a test can assert that a query did *not* run.

    >>> FakeSongRepository({1: Song(id=1, title="Oceans", artist="Hillsong")}).get_song_by_id(1)
    <Song: Oceans ------- Hillsong>
    """

    def __init__(
        self,
        songs: dict[int, Song] | None = None,
        usage: dict[int, SongUsage] | None = None,
        plays: list[Played] | None = None,
    ) -> None:
        self.songs = dict(songs or {})
        # Songs missing here are free: no plays, on no setlist.
        self.usage = dict(usage or {})
        # Unsaved Played rows the suggestion queries read.
        self.plays = list(plays or [])
        self.calls: list[str] = []

    def get_song_by_id(self, song_id: int) -> Song | None:
        return self.songs.get(song_id)

    def list_all_songs(self) -> QuerySet[Song]:
        raise _unused("list_all_songs")

    def list_all_played(self) -> QuerySet[Played]:
        raise _unused("list_all_played")

    def top_songs(self) -> list[dict[str, Any]]:
        raise _unused("top_songs")

    def top_tones(self) -> list[dict[str, Any]]:
        raise _unused("top_tones")

    def get_recent_song_ids(self, since: date) -> list[int]:
        return [p.song_id for p in self.plays if p.date >= since and p.song_id is not None]

    def get_played_by_ids(self, ids: list[int]) -> dict[int, Played]:
        return {p.id: p for p in self.plays if p.id in ids}

    def get_candidate_song_ids(
        self, position: int, before: date, exclude_song_ids: set[int]
    ) -> list[int]:
        self.calls.append("get_candidate_song_ids")
        return sorted(
            {
                p.song_id
                for p in self.plays
                if p.position == position
                and p.date < before
                and p.song_id is not None
                and p.song_id not in exclude_song_ids
            }
        )

    def get_latest_play(self, song_id: int, position: int) -> Played | None:
        matches = [p for p in self.plays if p.song_id == song_id and p.position == position]
        return max(matches, key=lambda p: (p.date, p.id), default=None)

    def get_songs_in_bulk(self, ids: set[int]) -> dict[int, Song]:
        raise _unused("get_songs_in_bulk")

    def bulk_create_played(self, items: list[Played]) -> list[Played]:
        raise _unused("bulk_create_played")

    def list_all_chord_charts(self) -> QuerySet[ChordChart]:
        raise _unused("list_all_chord_charts")

    def get_chord_chart_by_id(self, pk: int) -> ChordChart | None:
        raise _unused("get_chord_chart_by_id")

    def list_all_lyrics(self) -> QuerySet[Lyrics]:
        raise _unused("list_all_lyrics")

    def get_lyrics_by_id(self, pk: int) -> Lyrics | None:
        raise _unused("get_lyrics_by_id")

    def save_chord_chart(self, chart: ChordChart, fields: list[str]) -> None:
        raise _unused("save_chord_chart")

    def save_lyrics(self, lyrics: Lyrics, fields: list[str]) -> None:
        raise _unused("save_lyrics")

    def song_exists(self, title: str, artist: str, exclude_id: int | None = None) -> bool:
        self.calls.append("song_exists")
        pair = (title.lower(), artist.lower())
        return any(
            (song.title.lower(), song.artist.lower()) == pair
            for song_id, song in self.songs.items()
            if song_id != exclude_id
        )

    def create_song(self, new_song: NewSongInput) -> Song:
        raise _unused("create_song")

    def update_song(self, song: Song, changes: SongChangesInput) -> Song:
        self.calls.append("update_song")
        for field, value in changes.model_dump(exclude_unset=True).items():
            setattr(song, field, value)
        return song

    def get_song_usage(self, song_id: int) -> SongUsage:
        self.calls.append("get_song_usage")
        return self.usage.get(song_id, SongUsage(plays=0, setlist_dates=[]))

    def delete_song(self, song: Song) -> None:
        self.calls.append("delete_song")
        del self.songs[song.pk]

    def create_chord_chart(
        self, song: Song, content: str, tone: str, instrument: str
    ) -> ChordChart:
        raise _unused("create_chord_chart")

    def create_lyrics(self, song: Song, content: str) -> Lyrics:
        raise _unused("create_lyrics")
