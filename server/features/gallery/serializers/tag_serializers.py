from rest_framework import serializers


class _ClosedBody(serializers.Serializer[object]):
    """A body whose unknown keys are refused, so a client cannot believe it changed something the
    endpoint ignores (as ``PhotoUpdateSerializer``)."""

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        unknown = sorted(set(self.initial_data) - set(self.fields))
        if unknown:
            raise serializers.ValidationError(
                f"Fields not accepted: {unknown}. Accepted: {sorted(self.fields)}."
            )
        return attrs


class PhotoMembersReplaceSerializer(_ClosedBody):
    """``PUT /api/photos/{id}/members/``: the full new set; ``[]`` clears."""

    member_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=True)


class PhotoTagsBulkSerializer(_ClosedBody):
    """``POST /api/photos/members/``. Emptiness, overlap and the limit are domain rules, checked
    by the service, so their messages are the domain's (spec 015 FR-017, FR-018)."""

    photo_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=True)
    add_member_ids = serializers.ListField(
        child=serializers.IntegerField(), allow_empty=True, required=False, default=list
    )
    remove_member_ids = serializers.ListField(
        child=serializers.IntegerField(), allow_empty=True, required=False, default=list
    )


class TaggedMemberSerializer(serializers.Serializer[object]):
    """A member of the tagged-member list: exactly these three fields (spec 015 FR-035)."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    photo_count = serializers.IntegerField()
