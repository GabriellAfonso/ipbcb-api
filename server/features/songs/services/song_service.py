import random
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, NamedTuple

from django.db.models import QuerySet
from django.utils.timezone import now

from core.domain.exceptions import (
    ChordChartNotFoundError,
    DuplicateSongError,
    LyricsNotFoundError,
    ValidationError,
)
from core.metrics import CHORD_CHART_VIEWS_COUNTER, LYRICS_VIEWS_COUNTER
from features.songs.dtos import NewSongInput, SundaySetDTO, SundaySongDTO
from features.songs.models.chord_chart import ChordChart
from features.songs.models.lyrics import Lyrics
from features.songs.models.song import Played, Song
from features.songs.repositories.interfaces import SongRepository


class SuggestedPlay(NamedTuple):
    played: Played
    position: int


class SongService:
    def __init__(self, repository: SongRepository) -> None:
        self._repository = repository

    def list_all_songs(self) -> QuerySet[Song]:
        return self._repository.list_all_songs()

    def create_song(self, new_song: NewSongInput) -> Song:
        """Add a song to the catalogue, refusing a title+artist already there (any case).

        Check-then-insert: two simultaneous requests for the same song can both pass the
        check. No unique constraint backs it, since legacy rows may already repeat a pair.

        >>> service.create_song(NewSongInput(title="Oceans", artist="Hillsong"))
        <Song: Oceans ------- Hillsong>
        """
        if self._repository.song_exists(new_song.title, new_song.artist):
            raise DuplicateSongError(new_song.title, new_song.artist)
        return self._repository.create_song(new_song)

    def list_all_played(self) -> QuerySet[Played]:
        return self._repository.list_all_played()

    def list_played_by_sunday(self) -> list[SundaySetDTO]:
        """Return played songs grouped by Sunday date.

        >>> service.list_played_by_sunday()
        [SundaySetDTO(date='15/03/2026', songs=[...])]
        """
        grouped: dict[str, list[SundaySongDTO]] = defaultdict(list)

        for played in self._repository.list_all_played():
            date_str = played.date.strftime("%d/%m/%Y")
            grouped[date_str].append(
                SundaySongDTO(
                    song_id=played.song_id or 0,
                    position=played.position,
                    song=played.song.title if played.song else "",
                    artist=played.song.artist if played.song else "",
                    tone=played.tone,
                )
            )

        return [SundaySetDTO(date=day, songs=songs) for day, songs in grouped.items()]

    def top_songs(self) -> list[dict[str, Any]]:
        return self._repository.top_songs()

    def top_tones(self) -> list[dict[str, Any]]:
        return self._repository.top_tones()

    def suggest_songs(
        self,
        fixed_by_position: dict[int, int] | None = None,
    ) -> list[SuggestedPlay]:
        """Suggest songs for positions 1-4, respecting pinned positions.

        >>> service.suggest_songs({1: 42})  # pin position 1 to Played id=42
        [SuggestedPlay(played=..., position=1), ...]
        """
        fixed_by_position = fixed_by_position or {}
        three_months_ago = (now() - timedelta(days=90)).date()
        used_song_ids: set[int] = set()
        result: list[SuggestedPlay] = []

        recent_song_ids = set(self._repository.get_recent_song_ids(three_months_ago))

        if fixed_by_position:
            fixed_plays, used_song_ids = self._resolve_fixed(fixed_by_position)
            result.extend(fixed_plays)

        for position in range(1, 5):
            if position in fixed_by_position:
                continue
            play = self._pick_for_position(
                position,
                three_months_ago,
                recent_song_ids | used_song_ids,
            )
            if play:
                if play.song_id is not None:
                    used_song_ids.add(play.song_id)
                result.append(SuggestedPlay(played=play, position=position))

        result.sort(key=lambda x: x.position)
        return result

    def _resolve_fixed(
        self,
        fixed_by_position: dict[int, int],
    ) -> tuple[list[SuggestedPlay], set[int]]:
        fixed_ids = list(set(fixed_by_position.values()))
        fixed_by_id = self._repository.get_played_by_ids(fixed_ids)
        result: list[SuggestedPlay] = []
        used_song_ids: set[int] = set()

        for position, played_id in fixed_by_position.items():
            played_obj = fixed_by_id.get(played_id)
            if not played_obj:
                continue
            if played_obj.song_id is not None:
                used_song_ids.add(played_obj.song_id)
            result.append(SuggestedPlay(played=played_obj, position=position))

        return result, used_song_ids

    def _pick_for_position(
        self,
        position: int,
        before: date,
        exclude_song_ids: set[int],
    ) -> Played | None:
        qs = self._repository.get_eligible_plays(position, before, exclude_song_ids)
        if not qs.exists():
            return None
        return random.choice(list(qs))  # nosec B311

    def list_chord_charts(self) -> QuerySet[ChordChart]:
        CHORD_CHART_VIEWS_COUNTER.inc()
        return self._repository.list_all_chord_charts()

    def update_chord_chart_content(self, pk: int, content: str) -> ChordChart:
        """Update chord chart content by id.

        >>> service.update_chord_chart_content(1, "Am G C")
        <ChordChart: ...>
        """
        chart = self._repository.get_chord_chart_by_id(pk)
        if not chart:
            raise ChordChartNotFoundError(pk)
        chart.content = content
        self._repository.save_chord_chart(chart, ["content", "updated_at"])
        return chart

    def list_lyrics(self) -> QuerySet[Lyrics]:
        LYRICS_VIEWS_COUNTER.inc()
        return self._repository.list_all_lyrics()

    def update_lyrics_content(self, pk: int, content: str) -> Lyrics:
        """Update lyrics content by id.

        >>> service.update_lyrics_content(1, "Amazing grace")
        <Lyrics: ...>
        """
        lyrics = self._repository.get_lyrics_by_id(pk)
        if not lyrics:
            raise LyricsNotFoundError(pk)
        lyrics.content = content
        self._repository.save_lyrics(lyrics, ["content", "updated_at"])
        return lyrics

    def create_chord_chart(
        self, song_id: int, content: str, tone: str, instrument: str
    ) -> ChordChart:
        """Create a new chord chart for a song.

        >>> service.create_chord_chart(1, "{t:Amazing Grace}...", "G", "Violão")
        <ChordChart: ...>
        """
        if not content or not content.strip():
            raise ValidationError("Field 'content' is required.")
        if not tone or not tone.strip():
            raise ValidationError("Field 'tone' is required.")
        if not instrument or not instrument.strip():
            raise ValidationError("Field 'instrument' is required.")

        song = self._repository.get_song_by_id(song_id)
        if not song:
            raise ValidationError(f"Song not found: id={song_id}")

        return self._repository.create_chord_chart(song, content, tone, instrument)

    def create_lyrics(self, song_id: int, content: str) -> Lyrics:
        """Create lyrics for a song.

        >>> service.create_lyrics(1, "Amazing grace, how sweet the sound")
        <Lyrics: ...>
        """
        if not content or not content.strip():
            raise ValidationError("Field 'content' is required.")

        song = self._repository.get_song_by_id(song_id)
        if not song:
            raise ValidationError(f"Song not found: id={song_id}")

        return self._repository.create_lyrics(song, content)
