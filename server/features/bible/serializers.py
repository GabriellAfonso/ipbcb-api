"""OpenAPI shapes of the Bible videos and progress endpoints. Schema only: bodies are validated
by the Pydantic DTOs (``video_dtos``, ``progress_dtos``), which the Android client's generated
code must match (specs/025-bible-videos contracts/api.md)."""

from typing import Any

from rest_framework import serializers

from features.bible.domain.youtube_links import YouTubeKind
from features.bible.progress_dtos import MAX_SYNC_CHANGES


class BiblePlaceSerializer(serializers.Serializer[Any]):
    book = serializers.CharField(max_length=8)
    chapter = serializers.IntegerField(min_value=1, allow_null=True)


class BibleVideoPlaceSerializer(BiblePlaceSerializer):
    position = serializers.IntegerField()


class BibleVideoSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField()
    kind = serializers.ChoiceField(choices=[kind.value for kind in YouTubeKind])
    youtube_id = serializers.CharField()
    url = serializers.CharField()
    title = serializers.CharField()
    thumbnail_url = serializers.CharField()
    places = BibleVideoPlaceSerializer(many=True)


class BibleVideoCreateSerializer(serializers.Serializer[Any]):
    url = serializers.CharField()
    places = BiblePlaceSerializer(many=True)


class BibleVideoPlacesSerializer(serializers.Serializer[Any]):
    places = BiblePlaceSerializer(many=True)


class BibleVideoOrderSerializer(BiblePlaceSerializer):
    video_ids = serializers.ListField(child=serializers.IntegerField())


class BibleProgressStateSerializer(serializers.Serializer[Any]):
    chapters = serializers.DictField(child=serializers.ListField(child=serializers.IntegerField()))
    videos = serializers.ListField(child=serializers.IntegerField())


class BibleProgressChangeSerializer(serializers.Serializer[Any]):
    """``chapter`` items carry ``book`` and ``chapter``; ``video`` items carry ``video_id``."""

    type = serializers.ChoiceField(choices=["chapter", "video"])
    book = serializers.CharField(required=False, max_length=8)
    chapter = serializers.IntegerField(required=False)
    video_id = serializers.IntegerField(required=False)
    done = serializers.BooleanField()
    changed_at = serializers.DateTimeField()


class BibleProgressSyncSerializer(serializers.Serializer[Any]):
    changes = serializers.ListField(
        child=BibleProgressChangeSerializer(), min_length=1, max_length=MAX_SYNC_CHANGES
    )


class BibleProgressRejectedSerializer(serializers.Serializer[Any]):
    index = serializers.IntegerField()
    reason = serializers.CharField()


class BibleProgressSyncResultSerializer(serializers.Serializer[Any]):
    accepted = serializers.ListField(child=serializers.IntegerField())
    rejected = BibleProgressRejectedSerializer(many=True)
