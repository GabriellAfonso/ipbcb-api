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


class MemberRefSerializer(serializers.Serializer[object]):
    """A member as the gallery shows it. Exactly these two fields, listed by hand: member data
    is sensitive (constitution), and nothing else of the roll leaves the gallery
    (specs/015-gallery-member-tags FR-033, FR-035)."""

    id = serializers.IntegerField()
    name = serializers.CharField()


class PhotoSerializer(serializers.Serializer[object]):
    """The photo resource. Every field returned before feature 013 keeps its name and order;
    ``thumbnail_url`` was added by 013, ``position`` by 014, so a delta of the change feed
    carries the order on its own, ``members`` by 015, and the three media fields (last) by 023.
    For a video, ``image_url`` is the video file and ``thumbnail_url`` its poster."""

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
    members = MemberRefSerializer(many=True)
    media_type = serializers.CharField()
    duration_ms = serializers.IntegerField(allow_null=True)
    file_size = serializers.IntegerField(allow_null=True)

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


# PositiveIntegerField's ceiling on PostgreSQL; about 24 days, so no real video reaches it.
MAX_DURATION_MS = 2_147_483_647


class VideoUploadSerializer(serializers.Serializer[object]):
    """Types of a video upload's form fields (specs/023-gallery-videos FR-009). The view first
    checks each field was sent once: a ``QueryDict`` hands a serializer only one of the values."""

    video = serializers.FileField()
    poster = serializers.FileField()
    duration_ms = serializers.IntegerField(min_value=1, max_value=MAX_DURATION_MS)
    # Untrimmed, so a stray space is refused by the spec 016 shape check instead of dropped.
    client_upload_id = serializers.CharField(trim_whitespace=False)
    date_taken = serializers.DateField(required=False, allow_null=True)


class PhotoOrderSerializer(serializers.Serializer[object]):
    ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=True)
