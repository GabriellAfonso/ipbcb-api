import random
from collections import defaultdict
from collections.abc import Callable, Sequence
from datetime import date, timedelta
from typing import Any, NamedTuple

from django.db.models import QuerySet
from django.utils.timezone import now

from core.domain.exceptions import (
    ChordChartNotFoundError,
    DuplicateSongError,
    LyricsNotFoundError,
    SongInUseError,
    SongNotFoundError,
    ValidationError,
)
from core.metrics import CHORD_CHART_VIEWS_COUNTER, LYRICS_VIEWS_COUNTER
from features.songs.dtos import NewSongInput, SongChangesInput, SundaySetDTO, SundaySongDTO
from features.songs.models.chord_chart import ChordChart
from features.songs.models.lyrics import Lyrics
from features.songs.models.song import Played, Song
from features.songs.repositories.interfaces import SongRepository


# Draws one song id from the candidates. Injected so tests can see what the draw was offered.
SongPicker = Callable[[Sequence[int]], int]


class SuggestedPlay(NamedTuple):
    played: Played
    position: int


def _normalized_pair(title: str, artist: str) -> tuple[str, str]:
    return title.strip().lower(), artist.strip().lower()


def _pair_changed(song: Song, title: str, artist: str) -> bool:
    """>>> _pair_changed(Song(title="oceans", artist="Hillsong"), "Oceans ", "hillsong")
    False
    """
    return _normalized_pair(song.title, song.artist) != _normalized_pair(title, artist)


class SongService:
    def __init__(self, repository: SongRepository, pick_song: SongPicker = random.choice) -> None:
        # random.choice is not used for anything security-related (bandit B311).
        self._repository = repository
        self._pick_song = pick_song

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

    def update_song(self, song_id: int, changes: SongChangesInput) -> Song:
        """Apply a partial edit, refusing one that makes it repeat another song's pair.

        The duplicate check runs only when the title + artist pair changes once case and
        surrounding whitespace are ignored: legacy rows may already repeat a pair, and
        checking a link-only edit would leave such a song's link unfixable (spec 018
        FR-005). Same accepted race as ``create_song``.

        >>> service.update_song(42, SongChangesInput(title="Oceans"))
        <Song: Oceans ------- Hillsong>
        """
        song = self._require_song(song_id)
        title = changes.title if changes.title is not None else song.title
        artist = changes.artist if changes.artist is not None else song.artist
        if _pair_changed(song, title, artist) and self._repository.song_exists(
            title, artist, exclude_id=song.pk
        ):
            raise DuplicateSongError(title, artist)
        return self._repository.update_song(song, changes)

    def delete_song(self, song_id: int) -> None:
        """Delete a song nothing in the Sunday record points at; its chord charts and
        lyrics go with it. Usage is checked here; the repository covers a reference
        saved between this check and the delete.

        >>> service.delete_song(42)
        """
        song = self._require_song(song_id)
        usage = self._repository.get_song_usage(song.pk)
        if usage.in_use:
            raise SongInUseError(song.pk, song.title, usage.plays, usage.setlist_dates)
        self._repository.delete_song(song)

    def _require_song(self, song_id: int) -> Song:
        song = self._repository.get_song_by_id(song_id)
        if song is None:
            raise SongNotFoundError(song_id)
        return song

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
        excluded_by_position: dict[int, set[int]] | None = None,
    ) -> list[SuggestedPlay]:
        """Suggest songs for positions 1-4, respecting pinned positions and exclusions.

        ``fixed_by_position`` maps a position to a Played id; ``excluded_by_position`` maps a
        position to Song ids the app already showed there.

        >>> service.suggest_songs({1: 42}, {3: {12, 34}})
        [SuggestedPlay(played=..., position=1), ...]
        """
        fixed_by_position = fixed_by_position or {}
        before = (now() - timedelta(days=90)).date()
        result, used_song_ids = self._resolve_fixed(fixed_by_position)
        # Songs played recently and songs already on this Sunday are blocked for every
        # position and, unlike ``exclude``, never lifted by the fallback.
        blocked_song_ids = used_song_ids | set(self._repository.get_recent_song_ids(before))
        free_positions = [p for p in range(1, 5) if p not in fixed_by_position]
        result += self._draw_positions(
            free_positions, before, blocked_song_ids, excluded_by_position or {}
        )
        result.sort(key=lambda x: x.position)
        return result

    def _draw_positions(
        self,
        positions: list[int],
        before: date,
        blocked_song_ids: set[int],
        excluded_by_position: dict[int, set[int]],
    ) -> list[SuggestedPlay]:
        """Draw each position in order; a drawn song is blocked for the later ones."""
        drawn: list[SuggestedPlay] = []
        for position in positions:
            excluded = excluded_by_position.get(position, set())
            play = self._pick_for_position(position, before, blocked_song_ids, excluded)
            if play is None or play.song_id is None:
                continue
            blocked_song_ids.add(play.song_id)
            drawn.append(SuggestedPlay(played=play, position=position))
        return drawn

    def _resolve_fixed(
        self,
        fixed_by_position: dict[int, int],
    ) -> tuple[list[SuggestedPlay], set[int]]:
        if not fixed_by_position:
            return [], set()
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
        blocked_song_ids: set[int],
        excluded_song_ids: set[int],
    ) -> Played | None:
        """Draw a song for the position and return its latest play there.

        When ``excluded_song_ids`` empties the pool, draw again without it: the app sees
        the reset because a song it already showed comes back (no flag in the response).
        """
        song_id = self._draw_song(position, before, blocked_song_ids | excluded_song_ids)
        if song_id is None and excluded_song_ids:
            song_id = self._draw_song(position, before, blocked_song_ids)
        if song_id is None:
            return None
        return self._repository.get_latest_play(song_id, position)

    def _draw_song(self, position: int, before: date, exclude_song_ids: set[int]) -> int | None:
        candidates = self._repository.get_candidate_song_ids(position, before, exclude_song_ids)
        if not candidates:
            return None
        return self._pick_song(candidates)

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
