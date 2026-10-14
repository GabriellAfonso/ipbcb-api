from collections.abc import Iterator
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
from features.songs.dtos import NewSongInput, SongChangesInput
from features.songs.serializers.serializers import (
    ChordChartSerializer,
    LyricsSerializer,
    PlayedSerializer,
    SongSerializer,
)
from features.songs.services.song_service import SongService


# Caps `exclude` so a long or hostile query string never becomes an unbounded SQL IN.
MAX_EXCLUDE_PAIRS = 200


def _parse_position_pair(part: str) -> tuple[int, int] | None:
    """Parse one "position:id" entry; None when malformed or the position is outside 1-4.

    >>> _parse_position_pair(" 3 : 45 ")
    (3, 45)
    """
    if ":" not in part:
        return None
    pos_str, id_str = [x.strip() for x in part.split(":", 1)]
    try:
        pos, target_id = int(pos_str), int(id_str)
    except ValueError:
        return None
    if pos < 1 or pos > 4:
        return None
    return pos, target_id


def _iter_position_pairs(value: str) -> Iterator[tuple[int, int]]:
    """Valid (position, id) pairs of a comma-separated query param, in order."""
    for part in value.split(","):
        pair = _parse_position_pair(part.strip())
        if pair is not None:
            yield pair


def _parse_fixed_param(value: str) -> dict[int, int]:
    """Parse query param like: "1:12,3:45" -> {1: 12, 3: 45}.
    Invalid entries are ignored.

    >>> _parse_fixed_param("1:12,3:45")
    {1: 12, 3: 45}
    """
    return dict(_iter_position_pairs(value))


def _parse_exclude_param(value: str) -> dict[int, set[int]]:
    """Parse "3:12,3:34,1:7" -> {3: {12, 34}, 1: {7}}; ids are Song ids, not Played ids.

    Invalid entries are ignored; only the first MAX_EXCLUDE_PAIRS distinct pairs count.

    >>> _parse_exclude_param("3:12,3:34")
    {3: {12, 34}}
    """
    excluded: dict[int, set[int]] = {}
    seen: set[tuple[int, int]] = set()
    for pos, song_id in _iter_position_pairs(value):
        if len(seen) >= MAX_EXCLUDE_PAIRS:
            break
        seen.add((pos, song_id))
        excluded.setdefault(pos, set()).add(song_id)
    return excluded


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
        fixed_by_position = _parse_fixed_param(request.query_params.get("fixed", ""))
        excluded_by_position = _parse_exclude_param(request.query_params.get("exclude", ""))
        suggestions = song_service.suggest_songs(fixed_by_position, excluded_by_position)

        result = []
        for suggestion in suggestions:
            data = PlayedSerializer(suggestion.played).data
            data["position"] = suggestion.position
            result.append(data)

        return Response(result)


class AllSongsAPI(APIView):
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
        qs = song_service.list_all_songs()
        data = SongSerializer(qs, many=True).data
        return _not_modified_or_response(request, data)

    @inject
    def post(
        self,
        request: Request,
        song_service: SongService = Provide[Container.song_service],
    ) -> Response:
        # A body that fails NewSongInput raises pydantic's ValidationError, which the
        # exception handler turns into a 400 with field_errors.
        song = song_service.create_song(NewSongInput.model_validate(request.data))
        return Response(SongSerializer(song).data, status=201)


class SongDetailAPI(APIView):
    # No override: PATCH needs manage, like creating a song; DELETE needs owner (spec 018).
    permission_classes = [IsAuthenticated, scope_permission(Scope.SONGS)]

    @inject
    def patch(
        self,
        request: Request,
        pk: int,
        song_service: SongService = Provide[Container.song_service],
    ) -> Response:
        # A body that fails SongChangesInput raises pydantic's ValidationError, which the
        # exception handler turns into a 400 with field_errors.
        song = song_service.update_song(pk, SongChangesInput.model_validate(request.data))
        return Response(SongSerializer(song).data)

    @inject
    def delete(
        self,
        request: Request,
        pk: int,
        song_service: SongService = Provide[Container.song_service],
    ) -> Response:
        song_service.delete_song(pk)
        return Response(status=204)


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
