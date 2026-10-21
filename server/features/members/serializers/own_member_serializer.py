"""The caller's own roll record (specs/022-access-requests contracts/access-api.md). Fields listed
explicitly, never ``"__all__"`` (constitution, members domain)."""

from typing import Any

from rest_framework import serializers


class OwnMemberSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField()
    name = serializers.CharField()
    role = serializers.CharField(allow_null=True)
    ministries = serializers.ListField(child=serializers.CharField())
    birth_day = serializers.IntegerField(allow_null=True)
    birth_month = serializers.IntegerField(allow_null=True)
    birth_year = serializers.IntegerField(allow_null=True)
    baptism_date = serializers.DateField(allow_null=True)
    gender = serializers.CharField(allow_null=True)
