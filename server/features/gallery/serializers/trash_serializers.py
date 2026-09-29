from rest_framework import serializers

from features.gallery.dtos.trash_dtos import TrashEntry
from features.gallery.serializers.serializers import absolute_media_url


class TrashEntrySerializer(serializers.Serializer[object]):
    """One deletion batch in the trash (specs/014-gallery-trash-sync contract). Owners only, so
    it may name who deleted and who uploaded."""

    kind = serializers.CharField()
    id = serializers.IntegerField()
    name = serializers.CharField()
    deleted_at = serializers.DateTimeField()
    deleted_by = serializers.CharField(allow_null=True)
    uploaded_by = serializers.CharField(allow_null=True)
    purge_on = serializers.DateField()
    sub_album_count = serializers.IntegerField()
    photo_count = serializers.IntegerField()
    thumbnail_url = serializers.SerializerMethodField()

    def get_thumbnail_url(self, entry: TrashEntry) -> str | None:
        return absolute_media_url(self.context, entry.thumbnail_path)
