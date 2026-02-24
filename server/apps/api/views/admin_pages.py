import re
from datetime import datetime

from django.shortcuts import redirect, render
from django.views import View

from apps.persistence.models.songs import Played, Song
import random
from collections import defaultdict
from datetime import datetime, timedelta

from django.db import transaction
from django.db.models import Count
from django.utils.timezone import now
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.persistence.models.songs import Played, Song
from apps.api.serializers.serializers import PlayedSerializer

from .utils import _not_modified_or_response


class RegisterSundays(View):
    template_name = "main/register_sundays.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_staff:
            return redirect("main:unauthorized")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        notes = ["A", "A#", "Bb", "B", "C", "C#", "Db", "D",
                 "D#", "Eb", "E", "F", "F#", "Gb", "G", "G#", "Ab"]
        musics = Song.objects.all().order_by("title")
        context = {"notes": notes, "musics": musics}
        return render(request, self.template_name, context)

    def post(self, request):
        date_str = request.POST.get("date")

        if not date_str:
            return redirect("main:register_sundays")

        date_value = datetime.strptime(date_str, "%Y-%m-%d").date()

        musics = [
            (request.POST.get("first_music"),
             request.POST.get("tone_first_music"), 1),
            (request.POST.get("second_music"),
             request.POST.get("tone_second_music"), 2),
            (request.POST.get("third_music"),
             request.POST.get("tone_third_music"), 3),
            (request.POST.get("fourth_music"),
             request.POST.get("tone_fourth_music"), 4),
        ]

        for music_text, tone, position in musics:
            if not music_text:
                continue

            cleaned_title, artist = self.clean_music_title(music_text)

            song = (
                Song.objects.filter(title=cleaned_title, artist=artist).first()
                if artist
                else Song.objects.filter(title=cleaned_title).first()
            )
            if not song:
                continue

            Played.objects.create(
                song=song,
                date=date_value,
                tone=(tone or "").strip(),
                position=position,
            )

        return redirect("main:register_sundays")

    def clean_music_title(self, title: str):
        match = re.match(r"^(.*?)\s*\[(.*?)\]\s*$", title or "")
        if match:
            cleaned_title = match.group(1).strip()
            artist = match.group(2).strip()
            return cleaned_title, artist
        return (title or "").strip(), ""


class Unauthorized(View):
    def get(self, request):
        return render(request, "main/unauthorized.html")


class RegisterSundayPlaysAPI(APIView):
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

    def post(self, request):
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
            return Response({"detail": "Missing/invalid field: plays (must be a non-empty list)."}, status=400)

        try:
            date_value = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response({"detail": "Invalid date format. Use YYYY-MM-DD."}, status=400)

        cleaned_items: list[dict] = []
        song_ids: set[int] = set()

        for idx, item in enumerate(plays):
            if not isinstance(item, dict):
                return Response({"detail": f"plays[{idx}] must be an object."}, status=400)

            song_id = item.get("song_id")
            position = item.get("position")
            tone = (item.get("tone") or "").strip()

            try:
                song_id_int = int(song_id)
                position_int = int(position)
            except (TypeError, ValueError):
                return Response({"detail": f"plays[{idx}] song_id/position must be integers."}, status=400)

            if position_int < 1 or position_int > 4:
                return Response({"detail": f"plays[{idx}] position must be between 1 and 4."}, status=400)

            cleaned_items.append(
                {"song_id": song_id_int, "position": position_int, "tone": tone}
            )
            song_ids.add(song_id_int)

        songs_by_id = Song.objects.in_bulk(song_ids)
        missing = [sid for sid in sorted(song_ids) if sid not in songs_by_id]
        if missing:
            return Response({"detail": "Some songs were not found.", "missing_song_ids": missing}, status=400)

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
