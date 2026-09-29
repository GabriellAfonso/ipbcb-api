from rest_framework import serializers

from features.gallery.serializers.album_serializers import AlbumSerializer
from features.gallery.serializers.serializers import PhotoSerializer


class ChangeFeedSerializer(serializers.Serializer[object]):
    """The change feed body; ``albums`` and ``photos`` are the list endpoints' resources."""

    albums = AlbumSerializer(many=True)
    photos = PhotoSerializer(many=True)
    deleted_album_ids = serializers.ListField(child=serializers.IntegerField())
    deleted_photo_ids = serializers.ListField(child=serializers.IntegerField())
    cursor = serializers.CharField()
    full_sync_required = serializers.BooleanField()
