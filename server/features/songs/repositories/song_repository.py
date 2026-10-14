from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Count, ProtectedError, QuerySet

from core.domain.exceptions import SongInUseError
from features.songs.dtos import NewSongInput, SongChangesInput, SongUsage
from features.songs.models.chord_chart import ChordChart
from features.songs.models.lyrics import Lyrics
from features.songs.models.setlist import SetlistItem
from features.songs.models.song import Played, Song


class SongRepositoryImpl:
    """Song repository using Django ORM."""

    def list_all_songs(self) -> QuerySet[Song]:
        return Song.objects.select_related("category").order_by("title", "artist")

    def list_all_played(self) -> QuerySet[Played]:
        return Played.objects.select_related("song").order_by("-date", "position")

    def top_songs(self) -> list[dict[str, Any]]:
        return list(
            Played.objects.values("song_id", "song__title")
            .annotate(play_count=Count("song"))
            .order_by("-play_count")
        )

    def top_tones(self) -> list[dict[str, Any]]:
        return list(
            Played.objects.values("tone").annotate(tone_count=Count("tone")).order_by("-tone_count")
        )

    def get_recent_song_ids(self, since: date) -> list[int]:
        return list(Played.objects.filter(date__gte=since).values_list("song_id", flat=True))

    def get_played_by_ids(self, ids: list[int]) -> dict[int, Played]:
        qs = Played.objects.select_related("song").filter(id__in=ids)
        return {p.id: p for p in qs}

    def get_candidate_song_ids(
        self,
        position: int,
        before: date,
        exclude_song_ids: set[int],
    ) -> list[int]:
        """Distinct songs played in ``position`` before ``before``, ascending, one id each.

        One id per song, however often it was played, so the draw over them is uniform.

        >>> repo.get_candidate_song_ids(3, date(2026, 7, 16), {12})
        [5, 98, 301]
        """
        return list(
            Played.objects.filter(position=position, date__lt=before, song_id__isnull=False)
            .exclude(song_id__in=exclude_song_ids)
            .order_by("song_id")
            .values_list("song_id", flat=True)
            .distinct()
        )

    def get_latest_play(self, song_id: int, position: int) -> Played | None:
        """The song's most recent play in ``position``; it sets the suggested tone.

        >>> repo.get_latest_play(98, 3)
        <Played: Oceans ------- 01/02/2026>
        """
        return (
            Played.objects.select_related("song")
            .filter(song_id=song_id, position=position)
            .order_by("-date", "-id")
            .first()
        )

    def get_songs_in_bulk(self, ids: set[int]) -> dict[int, Song]:
        return Song.objects.in_bulk(ids)

    def bulk_create_played(self, items: list[Played]) -> list[Played]:
        return Played.objects.bulk_create(items)

    def list_all_chord_charts(self) -> QuerySet[ChordChart]:
        return ChordChart.objects.select_related("song").order_by("song__title")

    def get_chord_chart_by_id(self, pk: int) -> ChordChart | None:
        return ChordChart.objects.filter(pk=pk).first()

    def list_all_lyrics(self) -> QuerySet[Lyrics]:
        return Lyrics.objects.select_related("song").order_by("song__title")

    def get_lyrics_by_id(self, pk: int) -> Lyrics | None:
        return Lyrics.objects.filter(pk=pk).first()

    def save_chord_chart(self, chart: ChordChart, fields: list[str]) -> None:
        chart.save(update_fields=fields)

    def save_lyrics(self, lyrics: Lyrics, fields: list[str]) -> None:
        lyrics.save(update_fields=fields)

    def get_song_by_id(self, song_id: int) -> Song | None:
        return Song.objects.filter(pk=song_id).first()

    def song_exists(self, title: str, artist: str, exclude_id: int | None = None) -> bool:
        matches = Song.objects.filter(title__iexact=title, artist__iexact=artist)
        if exclude_id is not None:
            matches = matches.exclude(pk=exclude_id)
        return matches.exists()

    def create_song(self, new_song: NewSongInput) -> Song:
        return Song.objects.create(
            title=new_song.title, artist=new_song.artist, youtube_link=new_song.youtube_link
        )

    def update_song(self, song: Song, changes: SongChangesInput) -> Song:
        sent = changes.model_dump(exclude_unset=True)
        for field, value in sent.items():
            setattr(song, field, value)
        song.save(update_fields=list(sent))
        return song

    def get_song_usage(self, song_id: int) -> SongUsage:
        """Distinct play dates and setlist dates holding the song: its two PROTECT relations.

        >>> repo.get_song_usage(42)
        SongUsage(plays=7, setlist_dates=[datetime.date(2026, 10, 18)])
        """
        plays = Played.objects.filter(song_id=song_id).values("date").distinct().count()
        setlist_dates = (
            SetlistItem.objects.filter(song_id=song_id)
            .values_list("setlist__date", flat=True)
            .distinct()
            .order_by("setlist__date")
        )
        return SongUsage(plays=plays, setlist_dates=list(setlist_dates))

    def delete_song(self, song: Song) -> None:
        """Delete the song with its chord charts and lyrics (CASCADE), or refuse it in use.

        >>> repo.delete_song(song)
        """
        with self._translate_in_use(song):
            song.delete()

    @contextmanager
    def _translate_in_use(self, song: Song) -> Iterator[None]:
        """The service checks usage first; this catches a play or setlist saved after it.

        Two ways the database refuses: Django's collector raises ``ProtectedError`` for a
        reference already committed when it collects, and PostgreSQL's foreign keys are
        DEFERRABLE INITIALLY DEFERRED, so one committed after the collect fails as
        ``IntegrityError`` at commit. ``ATOMIC_REQUESTS`` is off, so this block is the
        outermost and its commit happens inside the ``try``. Anything not explained by a
        reference is re-raised rather than hidden.
        """
        try:
            with transaction.atomic():
                yield
        except (ProtectedError, IntegrityError) as exc:
            usage = self.get_song_usage(song.pk)
            if not usage.in_use:
                raise
            raise SongInUseError(song.pk, song.title, usage.plays, usage.setlist_dates) from exc

    def create_chord_chart(
        self, song: Song, content: str, tone: str, instrument: str
    ) -> ChordChart:
        return ChordChart.objects.create(
            song=song, content=content, tone=tone, instrument=instrument
        )

    def create_lyrics(self, song: Song, content: str) -> Lyrics:
        return Lyrics.objects.create(song=song, content=content)
