"""Input and output of the recovery e-mail and password recovery endpoints
(specs/028-password-recovery/contracts/recovery-api.md)."""

from typing import Any

from rest_framework import serializers

from core.application.dtos.account_dtos import (
    PasswordRecoveryConfirmDTO,
    PasswordRecoveryRequestDTO,
    RecoveryEmailChangeDTO,
)
from features.accounts.serializers.serializers import (
    REQUIRED_MESSAGES,
    NewPasswordSerializer,
    email_address_field,
)


def _code_field() -> serializers.CharField:
    # Any wrong shape is just a wrong code: only the length is capped, and that only to bound what
    # gets hashed. A dedicated format error would be a second answer to "wrong code".
    return serializers.CharField(max_length=32, error_messages={**REQUIRED_MESSAGES})


class RecoveryEmailChangeSerializer(serializers.Serializer[Any]):
    recovery_email = email_address_field()
    # No length rule, as in password change: it only has to match.
    current_password = serializers.CharField(
        write_only=True, trim_whitespace=False, error_messages={**REQUIRED_MESSAGES}
    )

    def create_dto(self) -> RecoveryEmailChangeDTO:
        return RecoveryEmailChangeDTO(
            recovery_email=self.validated_data["recovery_email"],
            current_password=self.validated_data["current_password"],
        )


class RecoveryEmailStateSerializer(serializers.Serializer[Any]):
    """What the signed-in recovery e-mail endpoints answer, same fields as the profile's."""

    recovery_email = serializers.CharField(source="recovery_email_or_none", allow_null=True)
    recovery_email_confirmed = serializers.BooleanField()


class RecoveryEmailConfirmSerializer(serializers.Serializer[Any]):
    code = _code_field()


class PasswordRecoveryRequestSerializer(serializers.Serializer[Any]):
    email = email_address_field()

    def create_dto(self) -> PasswordRecoveryRequestDTO:
        return PasswordRecoveryRequestDTO(email=self.validated_data["email"])


class PasswordRecoveryConfirmSerializer(NewPasswordSerializer):
    email = email_address_field()
    code = _code_field()

    def create_dto(self) -> PasswordRecoveryConfirmDTO:
        return PasswordRecoveryConfirmDTO(
            email=self.validated_data["email"],
            code=self.validated_data["code"],
            new_password=self.validated_data["new_password"],
        )
