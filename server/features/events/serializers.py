"""Event input and output fields, listed one by one (never ``"__all__"``).

Output is built from ``EventRecordDTO`` dumps; the public resource leaves the audit fields out
(specs/020-church-events/contracts/events-api.md).
"""

from typing import Any

from rest_framework import serializers

from features.events.domain.event_enums import EventVisibility
from features.events.models.event import LOCATION_MAX_LENGTH, TITLE_MAX_LENGTH

TIME_FORMAT = "%H:%M"
_VISIBILITY_CHOICES = [visibility.value for visibility in EventVisibility]


class EventPublicSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField()
    title = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField(allow_null=True)
    start_time = serializers.TimeField(format=TIME_FORMAT, allow_null=True)
    location = serializers.CharField(allow_null=True)
    description = serializers.CharField(allow_null=True)
    image_url = serializers.SerializerMethodField()
    visibility = serializers.ChoiceField(choices=_VISIBILITY_CHOICES)

    def get_image_url(self, obj: dict[str, Any]) -> str:
        """Absolute URL of the stored image; ``context`` carries the request and a storage
        URL builder so this layer never touches storage itself."""
        url_path = self.context["image_url_path"](obj["image_path"])
        return str(self.context["request"].build_absolute_uri(url_path))


class EventCreatorSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField(allow_blank=True)


class EventRecordSerializer(EventPublicSerializer):
    created_by = EventCreatorSerializer(allow_null=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class EventManagementListSerializer(serializers.Serializer[Any]):
    """OpenAPI only: the management list wraps the records."""

    events = EventRecordSerializer(many=True)


class EventWriteSerializer(serializers.Serializer[Any]):
    """Multipart fields of create and edit. ``""`` on a nullable date or time arrives as None
    (DRF ``allow_null`` on form input), which is how the app clears it.

    The image is read from ``request.FILES`` by the view and validated by the service, in the
    order of research R-04; the date rule is the service's too, so create and edit share it.
    """

    title = serializers.CharField(max_length=TITLE_MAX_LENGTH, trim_whitespace=True)
    start_date = serializers.DateField()
    end_date = serializers.DateField(required=False, allow_null=True)
    start_time = serializers.TimeField(required=False, allow_null=True, input_formats=[TIME_FORMAT])
    location = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=LOCATION_MAX_LENGTH
    )
    description = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    visibility = serializers.ChoiceField(choices=_VISIBILITY_CHOICES, required=False)


class EventWriteSchemaSerializer(EventWriteSerializer):
    """OpenAPI only: the multipart body with its file part."""

    image = serializers.ImageField(required=False)
