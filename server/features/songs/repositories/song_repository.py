from datetime import date
from typing import Any

from django.db.models import Count, QuerySet

from features.songs.dtos import NewSongInput
from features.songs.models.chord_chart import ChordChart
from features.songs.models.lyrics import Lyrics
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

    def get_eligible_plays(
        self,
        position: int,
        before: date,
        exclude_song_ids: set[int],
    ) -> QuerySet[Played]:
        return (
            Played.objects.select_related("song")
            .filter(position=position, date__lt=before)
            .exclude(song_id__in=exclude_song_ids)
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

    def song_exists(self, title: str, artist: str) -> bool:
        return Song.objects.filter(title__iexact=title, artist__iexact=artist).exists()

    def create_song(self, new_song: NewSongInput) -> Song:
        return Song.objects.create(
            title=new_song.title, artist=new_song.artist, youtube_link=new_song.youtube_link
        )

    def create_chord_chart(
        self, song: Song, content: str, tone: str, instrument: str
    ) -> ChordChart:
        return ChordChart.objects.create(
            song=song, content=content, tone=tone, instrument=instrument
        )

    def create_lyrics(self, song: Song, content: str) -> Lyrics:
        return Lyrics.objects.create(song=song, content=content)
