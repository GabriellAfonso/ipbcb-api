from datetime import datetime
from typing import Any

from django.db import transaction
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from features.accounts.permissions import IsAdminUser
from features.songs.models.song import Played, Song


# TODO Resolver essa gambiarra
class RegisterSundayPlaysAPI(APIView):
    permission_classes = [IsAdminUser]

    """
    POST: cria registros em Played para uma data.

    Requer: request.user autenticado e request.user.profile.is_admin == True

    Payload esperado:
    {
      "date": "2026-02-07",
      "plays": [
        {"song_id": 12, "position": 1, "tone": "G"},
        {"song_id": 55, "position": 2, "tone": "A#"}
      ]
    }
    """

    @staticmethod
    def post(request: Request) -> Response:
        user = request.user
        if not user or not getattr(user, "is_authenticated", False):
            return Response({"detail": "Authentication required."}, status=401)

        profile = getattr(user, "profile", None)
        if not profile or not getattr(profile, "is_admin", False):
            return Response({"detail": "Admin privileges required."}, status=403)

        payload = request.data or {}
        date_str = (payload.get("date") or "").strip()
        plays = payload.get("plays")

        if not date_str:
            return Response({"detail": "Missing field: date."}, status=400)
        if not isinstance(plays, list) or not plays:
            return Response(
                {"detail": "Missing/invalid field: plays (must be a non-empty list)."}, status=400
            )

        try:
            date_value = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response({"detail": "Invalid date format. Use YYYY-MM-DD."}, status=400)

        cleaned_items: list[dict[str, Any]] = []
        song_ids: set[int] = set()

        for idx, item in enumerate(plays):
            if not isinstance(item, dict):
                return Response({"detail": f"plays[{idx}] must be an object."}, status=400)

            song_id = item.get("song_id")
            position = item.get("position")
            tone = (item.get("tone") or "").strip()

            if song_id is None or position is None:
                return Response(
                    {"detail": f"plays[{idx}] song_id/position must be integers."}, status=400
                )

            try:
                song_id_int = int(song_id)
                position_int = int(position)
            except (TypeError, ValueError):
                return Response(
                    {"detail": f"plays[{idx}] song_id/position must be integers."}, status=400
                )

            if position_int < 1 or position_int > 10:
                return Response(
                    {"detail": f"plays[{idx}] position must be between 1 and 10."}, status=400
                )

            cleaned_items.append({"song_id": song_id_int, "position": position_int, "tone": tone})
            song_ids.add(song_id_int)

        songs_by_id = Song.objects.in_bulk(song_ids)
        missing = [sid for sid in sorted(song_ids) if sid not in songs_by_id]
        if missing:
            return Response(
                {"detail": "Some songs were not found.", "missing_song_ids": missing}, status=400
            )

        to_create: list[Played] = [
            Played(
                song=songs_by_id[item["song_id"]],
                date=date_value,
                tone=item["tone"],
                position=item["position"],
            )
            for item in cleaned_items
        ]

        with transaction.atomic():
            Played.objects.bulk_create(to_create)

        return Response({"created": len(to_create)}, status=201)
