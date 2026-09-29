from typing import Any

from dependency_injector.wiring import Provide, inject
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from config.di import Container
from core.domain.access import Scope
from core.domain.exceptions import ValidationError
from core.http.parsing import require_int
from core.http.permissions import scope_permission
from core.http.utils import _not_modified_or_response
from features.songs.serializers.serializers import (
    ChordChartSerializer,
    LyricsSerializer,
    PlayedSerializer,
    SongSerializer,
)
from features.songs.services.song_service import SongService


def _parse_fixed_param(value: str) -> dict[int, int]:
    """Parse query param like: "1:12,3:45" -> {1: 12, 3: 45}.
    Invalid entries are ignored.

    >>> _parse_fixed_param("1:12,3:45")
    {1: 12, 3: 45}
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
    permission_classes = [AllowAny]

    @inject
    def get(
        self,
        request: Request,
        song_service: SongService = Provide[Container.song_service],
    ) -> Response:
        result = song_service.list_played_by_sunday()
        return _not_modified_or_response(
            request,
            [s.model_dump() for s in result],
        )


class TopSongsAPI(APIView):
    permission_classes = [AllowAny]

    @inject
    def get(
        self,
        request: Request,
        song_service: SongService = Provide[Container.song_service],
    ) -> Response:
        result = song_service.top_songs()
        return _not_modified_or_response(request, result)


class TopTonesAPI(APIView):
    permission_classes = [AllowAny]

    @inject
    def get(
        self,
        request: Request,
        song_service: SongService = Provide[Container.song_service],
    ) -> Response:
        result = song_service.top_tones()
        return _not_modified_or_response(request, result)


class SuggestedSongsAPI(APIView):
    permission_classes = [AllowAny]

    @inject
    def get(
        self,
        request: Request,
        song_service: SongService = Provide[Container.song_service],
    ) -> Response:
        fixed_param = request.query_params.get("fixed", "")
        fixed_by_position = _parse_fixed_param(fixed_param)
        suggestions = song_service.suggest_songs(fixed_by_position)

        result = []
        for suggestion in suggestions:
            data = PlayedSerializer(suggestion.played).data
            data["position"] = suggestion.position
            result.append(data)

        return Response(result)


class AllSongsAPI(APIView):
    permission_classes = [AllowAny]

    @inject
    def get(
        self,
        request: Request,
        song_service: SongService = Provide[Container.song_service],
    ) -> Response:
        qs = song_service.list_all_songs()
        data = SongSerializer(qs, many=True).data
        return _not_modified_or_response(request, data)


class ChordChartListAPI(APIView):
    def get_permissions(self) -> list[Any]:
        if self.request.method == "POST":
            return [IsAuthenticated(), scope_permission(Scope.SONGS)()]
        return [AllowAny()]

    @inject
    def get(
        self,
        request: Request,
        song_service: SongService = Provide[Container.song_service],
    ) -> Response:
        qs = song_service.list_chord_charts()
        data = ChordChartSerializer(qs, many=True).data
        return Response(data)

    @inject
    def post(
        self,
        request: Request,
        song_service: SongService = Provide[Container.song_service],
    ) -> Response:
        song_id = request.data.get("song_id")
        if song_id is None:
            raise ValidationError("Field 'song_id' is required.")
        content = request.data.get("content", "")
        tone = request.data.get("tone", "")
        instrument = request.data.get("instrument", "")
        chart = song_service.create_chord_chart(
            require_int(song_id, "song_id"), content, tone, instrument
        )
        return Response(ChordChartSerializer(chart).data, status=201)


class LyricsListAPI(APIView):
    def get_permissions(self) -> list[Any]:
        if self.request.method == "POST":
            return [IsAuthenticated(), scope_permission(Scope.SONGS)()]
        return [AllowAny()]

    @inject
    def get(
        self,
        request: Request,
        song_service: SongService = Provide[Container.song_service],
    ) -> Response:
        qs = song_service.list_lyrics()
        data = LyricsSerializer(qs, many=True).data
        return Response(data)

    @inject
    def post(
        self,
        request: Request,
        song_service: SongService = Provide[Container.song_service],
    ) -> Response:
        song_id = request.data.get("song_id")
        if song_id is None:
            raise ValidationError("Field 'song_id' is required.")
        content = request.data.get("content", "")
        lyrics = song_service.create_lyrics(require_int(song_id, "song_id"), content)
        return Response(LyricsSerializer(lyrics).data, status=201)


class ChordChartDetailAPI(APIView):
    permission_classes = [IsAuthenticated, scope_permission(Scope.SONGS)]

    @inject
    def patch(
        self,
        request: Request,
        pk: int,
        song_service: SongService = Provide[Container.song_service],
    ) -> Response:
        content = request.data.get("content")
        if content is None:
            raise ValidationError("Field 'content' is required.")
        chart = song_service.update_chord_chart_content(pk, content)
        return Response(ChordChartSerializer(chart).data)


class LyricsDetailAPI(APIView):
    permission_classes = [IsAuthenticated, scope_permission(Scope.SONGS)]

    @inject
    def patch(
        self,
        request: Request,
        pk: int,
        song_service: SongService = Provide[Container.song_service],
    ) -> Response:
        content = request.data.get("content")
        if content is None:
            raise ValidationError("Field 'content' is required.")
        lyrics = song_service.update_lyrics_content(pk, content)
        return Response(LyricsSerializer(lyrics).data)
