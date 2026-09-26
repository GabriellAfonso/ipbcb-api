"""Leader member endpoints: explicit input and output fields, never ``"__all__"``.

Member data is sensitive (constitution, Security): a field reaches the app only if it is
listed here, and a key the app sends that is not listed is refused rather than ignored.
"""

from typing import Any

from rest_framework import serializers
from rest_framework.request import Request


def build_photo_url(request: Request, photo_path: str | None) -> str | None:
    """Absolute URL for a stored photo path, as ``ProfileSerializer`` builds it.

    >>> build_photo_url(request, "/ipbcb/media/members/6f1c.jpg")
    'https://host/ipbcb/media/members/6f1c.jpg'
    """
    return request.build_absolute_uri(photo_path) if photo_path else None


class NamedRefSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField()
    name = serializers.CharField()


class _PhotoUrlMixin(serializers.Serializer[Any]):
    photo_url = serializers.SerializerMethodField()

    def get_photo_url(self, obj: dict[str, Any]) -> str | None:
        return build_photo_url(self.context["request"], obj["photo_path"])


class MemberSummarySerializer(_PhotoUrlMixin):
    id = serializers.IntegerField()
    name = serializers.CharField()
    status = NamedRefSerializer(allow_null=True)
    is_active = serializers.BooleanField()


class MemberRecordSerializer(_PhotoUrlMixin):
    id = serializers.IntegerField()
    name = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    birth_date = serializers.DateField(allow_null=True)
    gender = serializers.CharField(allow_null=True)
    status = NamedRefSerializer(allow_null=True)
    role = NamedRefSerializer(allow_null=True)
    ministries = NamedRefSerializer(many=True)
    baptism_date = serializers.DateField(allow_null=True)
    is_active = serializers.BooleanField()
    created_at = serializers.DateTimeField()


class MemberOptionsSerializer(serializers.Serializer[Any]):
    statuses = NamedRefSerializer(many=True)
    roles = NamedRefSerializer(many=True)
    ministries = NamedRefSerializer(many=True)


class ChangeLogEditorSerializer(serializers.Serializer[Any]):
    id = serializers.CharField()
    name = serializers.CharField()


class ChangeLogEntrySerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField()
    editor = ChangeLogEditorSerializer(allow_null=True)
    field = serializers.CharField()
    old_value = serializers.CharField(allow_null=True)
    new_value = serializers.CharField(allow_null=True)
    changed_at = serializers.DateTimeField()


class MemberPatchSerializer(serializers.Serializer[Any]):
    """Shape of a partial edit. Existence of ids and date rules are the service's job."""

    name = serializers.CharField(max_length=255, required=False)
    first_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    birth_date = serializers.DateField(required=False, allow_null=True)
    gender = serializers.ChoiceField(choices=["M", "F"], required=False, allow_null=True)
    status_id = serializers.IntegerField(required=False, allow_null=True)
    role_id = serializers.IntegerField(required=False, allow_null=True)
    ministry_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    baptism_date = serializers.DateField(required=False, allow_null=True)
    is_active = serializers.BooleanField(required=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        unknown = sorted(set(self.initial_data) - set(self.fields))
        if unknown:
            raise serializers.ValidationError(
                f"Campos não aceitos: {unknown}. Aceitos: {sorted(self.fields)}."
            )
        return attrs


class MemberCreateSerializer(MemberPatchSerializer):
    name = serializers.CharField(max_length=255)
