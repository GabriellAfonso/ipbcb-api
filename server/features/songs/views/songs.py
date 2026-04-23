import random
from collections import defaultdict
from datetime import timedelta
from typing import Any

from django.db.models import Count
from django.utils.timezone import now
from rest_framework.generics import ListAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from features.songs.models.chord_chart import ChordChart
from features.songs.models.lyrics import Lyrics
from features.songs.models.song import Played, Song
from features.songs.serializers.serializers import (
    PlayedSerializer,
    ChordChartSerializer,
    LyricsSerializer,
)
from features.core.http.utils import _not_modified_or_response


def _parse_fixed_param(value: str) -> dict[int, int]:
    """
    Parses query param like: "1:12,3:45" -> {1: 12, 3: 45}
    Invalid entries are ignored.
    """
    fixed: dict[int, int] = {}
    if not value:
        return fixed

    parts = [p.strip() for p in value.split(",") if p.strip()]
    for part in parts:
        if ":" not in part:
            continue
        pos_str, played_id_str = [x.strip() for x in part.split(":", 1)]
        try:
            pos = int(pos_str)
            played_id = int(played_id_str)
        except ValueError:
            continue

        if pos < 1 or pos > 4:
            continue

        fixed[pos] = played_id

    return fixed


class SongsBySundayAPI(APIView):
    serializer_class = PlayedSerializer

    def get(self, request: Request) -> Response:
        qs = Played.objects.select_related("song").order_by("-date", "position")

        data = PlayedSerializer(qs, many=True).data
        grouped: dict[str, list[Any]] = defaultdict(list)

        for item in data:
            grouped[item["date"]].append(
                {
                    "position": item["position"],
                    "song": item["song"]["title"],
                    "artist": item["song"]["artist"],
                    "tone": item["tone"],
                }
            )

        result = [{"date": day, "songs": songs} for day, songs in grouped.items()]
        return _not_modified_or_response(request, result)


class TopSongsAPI(APIView):
    def get(self, request: Request) -> Response:
        qs = (
            Played.objects.values("song__title")
            .annotate(play_count=Count("song"))
            .order_by("-play_count")
        )
        result = list(qs)
        return _not_modified_or_response(request, result)


class TopTonesAPI(APIView):
    def get(self, request: Request) -> Response:
        qs = (
            Played.objects.values("tone").annotate(tone_count=Count("tone")).order_by("-tone_count")
        )
        result = list(qs)
        return _not_modified_or_response(request, result)


class SuggestedSongsAPI(APIView):
    def get(self, request: Request) -> Response:
        fixed_param = request.query_params.get("fixed", "")
        fixed_by_position = _parse_fixed_param(fixed_param)
        suggested = self.get_suggested_songs(fixed_by_position)
        return Response(suggested)

    def get_suggested_songs(self, fixed_by_position: dict[int, int] | None = None) -> list[Any]:
        three_months_ago = now() - timedelta(days=90)
        suggested: list[Any] = []
        used_song_ids: set[int] = set()

        fixed_by_position = fixed_by_position or {}

        recent_songs = Played.objects.filter(date__gte=three_months_ago).values_list(
            "song_id", flat=True
        )

        if fixed_by_position:
            fixed_ids = list(set(fixed_by_position.values()))
            fixed_playeds = Played.objects.select_related("song").filter(id__in=fixed_ids)
            fixed_by_id = {p.id: p for p in fixed_playeds}

            for position, played_id in fixed_by_position.items():
                played_obj = fixed_by_id.get(played_id)
                if not played_obj:
                    continue

                if played_obj.song_id is not None:
                    used_song_ids.add(played_obj.song_id)

                data = PlayedSerializer(played_obj).data
                data["position"] = position
                suggested.append(data)

        for position in range(1, 5):
            if position in fixed_by_position:
                continue

            qs = (
                Played.objects.select_related("song")
                .filter(position=position, date__lt=three_months_ago)
                .exclude(song_id__in=recent_songs)
                .exclude(song_id__in=used_song_ids)
            )

            if qs.exists():
                chosen = random.choice(list(qs))
                if chosen.song_id is not None:
                    used_song_ids.add(chosen.song_id)

                data = PlayedSerializer(chosen).data
                data["position"] = position
                suggested.append(data)

        suggested.sort(key=lambda x: x.get("position", 0))
        return suggested


class AllSongsAPI(APIView):
    def get(self, request: Request) -> Response:
        qs = (
            Song.objects.select_related("category")
            .order_by("title", "artist")
            .values("id", "title", "artist", "category__name")
        )

        data = [
            {
                "id": row["id"],
                "title": row["title"],
                "artist": row["artist"],
                "category": row["category__name"] or "",
            }
            for row in qs
        ]
        return _not_modified_or_response(request, data, tag="all-songs")


class ChordChartListView(ListAPIView[ChordChart]):
    serializer_class = ChordChartSerializer
    queryset = ChordChart.objects.select_related("song").all()


class LyricsListView(ListAPIView[Lyrics]):
    serializer_class = LyricsSerializer
    queryset = Lyrics.objects.select_related("song").all()
