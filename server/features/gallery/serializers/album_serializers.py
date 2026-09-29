from rest_framework import serializers

from features.gallery.dtos.gallery_dtos import AlbumView
from features.gallery.serializers.serializers import absolute_media_url


class AlbumSerializer(serializers.Serializer[object]):
    """The album resource; ``cover_url`` is the resolved cover, possibly a sub-album's.
    ``position`` (last) was added by feature 014."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    parent_id = serializers.IntegerField(allow_null=True)
    description = serializers.CharField()
    event_date = serializers.DateField(allow_null=True)
    cover_url = serializers.SerializerMethodField()
    cover_source_album_id = serializers.IntegerField(allow_null=True)
    position = serializers.IntegerField()

    def get_cover_url(self, album: AlbumView) -> str | None:
        return absolute_media_url(self.context, album.cover_path)


class AlbumCreateSerializer(serializers.Serializer[object]):
    name = serializers.CharField(max_length=100)
    parent_id = serializers.IntegerField(required=False, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True)
    event_date = serializers.DateField(required=False, allow_null=True)


class AlbumUpdateSerializer(AlbumCreateSerializer):
    """Every field optional; ``validated_data`` holds only the keys sent, which is how the
    service tells "do not move" from "move to the root"."""

    name = serializers.CharField(max_length=100, required=False)


class AlbumOrderSerializer(serializers.Serializer[object]):
    parent_id = serializers.IntegerField(allow_null=True)
    ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=True)
