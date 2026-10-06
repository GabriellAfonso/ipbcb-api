from datetime import date, datetime
from typing import Any, Protocol
from uuid import UUID

from django.db.models import QuerySet

from features.songs.hymnal_history_dtos import ServiceWindowDTO
from features.songs.models.chord_chart import ChordChart
from core.models import ChurchService
from features.songs.models.hymnal_history import (
    HymnalHistorySettings,
    HymnalViewEvent,
)
from features.songs.models.lyrics import Lyrics
from features.songs.models.song import Played, Song
from features.songs.setlist_dtos import SetlistDTO, SetlistItemInput


class SongRepository(Protocol):
    """Contract for song persistence operations."""

    def list_all_songs(self) -> QuerySet[Song]: ...

    def list_all_played(self) -> QuerySet[Played]: ...

    def top_songs(self) -> list[dict[str, Any]]: ...

    def top_tones(self) -> list[dict[str, Any]]: ...

    def get_recent_song_ids(self, since: date) -> list[int]: ...

    def get_played_by_ids(self, ids: list[int]) -> dict[int, Played]: ...

    def get_eligible_plays(
        self,
        position: int,
        before: date,
        exclude_song_ids: set[int],
    ) -> QuerySet[Played]: ...

    def get_songs_in_bulk(self, ids: set[int]) -> dict[int, Song]: ...

    def bulk_create_played(self, items: list[Played]) -> list[Played]: ...

    def list_all_chord_charts(self) -> QuerySet[ChordChart]: ...

    def get_chord_chart_by_id(self, pk: int) -> ChordChart | None: ...

    def list_all_lyrics(self) -> QuerySet[Lyrics]: ...

    def get_lyrics_by_id(self, pk: int) -> Lyrics | None: ...

    def save_chord_chart(self, chart: ChordChart, fields: list[str]) -> None: ...

    def save_lyrics(self, lyrics: Lyrics, fields: list[str]) -> None: ...

    def get_song_by_id(self, song_id: int) -> Song | None: ...

    def create_chord_chart(
        self, song: Song, content: str, tone: str, instrument: str
    ) -> ChordChart: ...

    def create_lyrics(self, song: Song, content: str) -> Lyrics: ...


class HymnalRepository(Protocol):
    """Contract for hymnal persistence operations."""

    def list_all_hymns(self) -> list[dict[str, Any]]: ...


class HymnalHistoryRepository(Protocol):
    """Contract for hymnal view history persistence.

    Every method is bulk by design: ingest must cost a constant number of queries
    regardless of batch size.
    """

    def get_existing_client_event_ids(self, client_event_ids: list[UUID]) -> set[UUID]: ...

    def get_collapse_candidates(
        self,
        pairs: set[tuple[int, str]],
        window_start: datetime,
        window_end: datetime,
    ) -> list[tuple[int, str, datetime]]: ...

    def get_existing_hymn_ids(self, hymn_ids: set[int]) -> set[int]: ...

    def bulk_create_events(self, events: list[HymnalViewEvent]) -> None: ...

    def list_events_in_range(
        self,
        start: datetime | None,
        end: datetime | None,
    ) -> list[tuple[int, datetime, str]]: ...

    def get_hymn_labels(self, hymn_ids: set[int]) -> dict[int, tuple[str, str]]: ...

    def list_active_service_windows(self) -> list[ChurchService]: ...

    def list_service_windows(self) -> list[ChurchService]: ...

    def get_service_window(self, window_id: int) -> ChurchService | None: ...

    def create_service_window(self, data: ServiceWindowDTO) -> ChurchService: ...

    def update_service_window(
        self,
        window: ChurchService,
        changes: dict[str, Any],
    ) -> ChurchService: ...

    def delete_service_window(self, window: ChurchService) -> None: ...

    def get_settings(self) -> HymnalHistorySettings: ...

    def update_settings(self, changes: dict[str, int]) -> HymnalHistorySettings: ...


class SongLookup(Protocol):
    """The one song query a setlist save needs; ``SongRepositoryImpl`` satisfies it."""

    def get_songs_in_bulk(self, ids: set[int]) -> dict[int, Song]: ...


class SetlistRepository(Protocol):
    """Contract for Sunday setlist persistence (specs/017-sunday-setlist-push)."""

    def replace(
        self, day: date, author_id: UUID, items: list[SetlistItemInput], saved_at: datetime
    ) -> tuple[SetlistDTO, bool]: ...

    def delete(self, day: date) -> bool: ...

    def get_by_date(self, day: date) -> SetlistDTO | None: ...

    def current(self, today: date) -> SetlistDTO | None: ...

    def pending(self, today: date) -> list[SetlistDTO]: ...

    def has_plays(self, day: date) -> bool: ...

    def claim_reminder_slot(self, day: date, slot: datetime) -> bool: ...
