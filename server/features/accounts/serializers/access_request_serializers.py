"""Access requests and "Perfis" (specs/022-access-requests contracts/access-api.md). Fields listed
explicitly; no e-mail anywhere (spec FR-019)."""

from typing import Any

from django.utils.timezone import localtime
from rest_framework import serializers
from rest_framework.request import Request

from features.accounts.domain.access_requests import (
    DENIAL_REASON_MAX_LENGTH,
    MESSAGE_MAX_LENGTH,
    AccessRequestType,
)
from features.accounts.dtos import AccessRequestCreateDTO, ManagedAccountPatchDTO
from features.accounts.serializers.serializers import CHURCH_TIME_ZONE


def _reject_unknown_fields(serializer: serializers.Serializer[Any]) -> None:
    unknown = sorted(set(serializer.initial_data) - set(serializer.fields))
    if unknown:
        raise serializers.ValidationError(
            f"Campos não aceitos: {unknown}. Aceitos: {sorted(serializer.fields)}."
        )


class AccessRequestCreateSerializer(serializers.Serializer[Any]):
    type = serializers.ChoiceField(choices=[kind.value for kind in AccessRequestType])
    message = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=MESSAGE_MAX_LENGTH
    )

    def create_dto(self) -> AccessRequestCreateDTO:
        """>>> serializer.create_dto().type
        <AccessRequestType.ACCESS: 'access'>
        """
        return AccessRequestCreateDTO(
            type=AccessRequestType(self.validated_data["type"]),
            message=self.validated_data.get("message"),
        )


class AccessDenySerializer(serializers.Serializer[Any]):
    reason = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=DENIAL_REASON_MAX_LENGTH
    )


class ManagedAccountPatchSerializer(serializers.Serializer[Any]):
    access_requests_blocked = serializers.BooleanField(required=False)
    member_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        # A typo ("blocked") must not answer 200 having changed nothing.
        _reject_unknown_fields(self)
        return attrs

    def create_dto(self) -> ManagedAccountPatchDTO:
        """Only the keys sent, so ``model_fields_set`` tells "leave alone" from "unlink"."""
        return ManagedAccountPatchDTO(**self.validated_data)


class PersonRefSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()


class AccessRequestRecordSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField()
    type = serializers.CharField()
    message = serializers.CharField(allow_null=True)
    status = serializers.CharField()
    created_at = serializers.DateTimeField()
    decided_by = PersonRefSerializer(allow_null=True)
    decided_at = serializers.DateTimeField(allow_null=True)
    denial_reason = serializers.CharField(allow_null=True)


class LinkedMemberSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField()
    name = serializers.CharField()


class ManagedAccountSerializer(serializers.Serializer[Any]):
    """Needs ``context["request"]`` for the absolute photo URL."""

    id = serializers.UUIDField()
    name = serializers.CharField()
    username = serializers.CharField()
    photo_url = serializers.SerializerMethodField()
    member_access = serializers.BooleanField()
    access_via_role = serializers.BooleanField()
    access_requests_blocked = serializers.BooleanField()
    access_granted_by = PersonRefSerializer(allow_null=True)
    access_granted_at = serializers.DateTimeField(allow_null=True)
    member = LinkedMemberSerializer(allow_null=True)
    date_joined = serializers.SerializerMethodField()
    pending_requests = AccessRequestRecordSerializer(many=True)

    def get_photo_url(self, obj: dict[str, Any]) -> str | None:
        request: Request | None = self.context.get("request")
        path = obj.get("photo_path")
        return request.build_absolute_uri(path) if path and request else None

    def get_date_joined(self, obj: dict[str, Any]) -> str:
        """Same format as ``/me`` (specs/021-user-account): the date in the church's zone."""
        return localtime(obj["date_joined"], CHURCH_TIME_ZONE).date().isoformat()


class ManagedAccountDetailSerializer(ManagedAccountSerializer):
    requests = AccessRequestRecordSerializer(many=True)
