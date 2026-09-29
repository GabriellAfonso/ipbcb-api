from rest_framework import serializers
from rest_framework.request import Request

from features.gallery.dtos.gallery_dtos import PhotoView


def absolute_media_url(context: dict[str, object], path: str | None) -> str | None:
    """Absolute URI of a stored file's URL path, or None without a path or a request.

    >>> absolute_media_url({"request": request}, "/ipbcb/media/gallery/7/x.jpg")
    'http://host/ipbcb/media/gallery/7/x.jpg'
    """
    request = context.get("request")
    if not path or not isinstance(request, Request):
        return None
    return request.build_absolute_uri(path)


class PhotoSerializer(serializers.Serializer[object]):
    """The photo resource. Every field returned before feature 013 keeps its name and order;
    ``thumbnail_url`` was added by 013 and ``position`` (last) by 014, so a delta of the change
    feed carries the order on its own."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    description = serializers.CharField()
    album_id = serializers.IntegerField()
    album_name = serializers.CharField()
    image_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    date_taken = serializers.DateField(allow_null=True)
    uploaded_at = serializers.DateTimeField()
    position = serializers.IntegerField()

    def get_image_url(self, photo: PhotoView) -> str | None:
        return absolute_media_url(self.context, photo.image_path)

    def get_thumbnail_url(self, photo: PhotoView) -> str | None:
        return absolute_media_url(self.context, photo.thumbnail_path)


class RejectedFileSerializer(serializers.Serializer[object]):
    filename = serializers.CharField()
    reason = serializers.CharField()


class PhotoUpdateSerializer(serializers.Serializer[object]):
    """PATCH body of a photo. Any other key — the image included — is refused, so a client
    cannot believe it changed something the endpoint ignores."""

    name = serializers.CharField(required=False, max_length=100)
    description = serializers.CharField(required=False, allow_blank=True)
    date_taken = serializers.DateField(required=False, allow_null=True)
    album_id = serializers.IntegerField(required=False)

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        unknown = sorted(set(self.initial_data) - set(self.fields))
        if unknown:
            raise serializers.ValidationError(
                f"Fields not accepted: {unknown}. Editable: {sorted(self.fields)}."
            )
        return attrs


class PhotoOrderSerializer(serializers.Serializer[object]):
    ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=True)
