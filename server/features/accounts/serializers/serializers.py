from typing import Any, TypedDict

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.request import Request

from features.accounts.models.profile import Profile
from features.accounts.validators import USERNAME_RULE_MESSAGE, is_valid_username
from features.accounts.models.user import User
from core.application.dtos.access_dtos import AccessGrantsDTO
from core.application.dtos.auth_dtos import RegisterDTO
from core.domain.access import ROLE_DISPLAY_NAMES, Scope


class RegisterData(TypedDict):
    username: str
    first_name: str
    last_name: str
    password: str
    password_confirm: str


class RegisterSerializer(serializers.Serializer[RegisterData]):
    username = serializers.CharField(
        max_length=150,
        error_messages={
            "blank": _("Este campo não pode ficar em branco."),
            "required": _("Este campo é obrigatório."),
        },
    )

    def validate_username(self, value: str) -> str:
        # Order matters: "ADMIN" is only valid once lowercased.
        normalized = value.strip().lower()
        if not is_valid_username(normalized):
            raise serializers.ValidationError(USERNAME_RULE_MESSAGE)
        if User.objects.filter(username=normalized).exists():
            raise serializers.ValidationError(_("Este nome de usuário já está em uso."))
        return normalized

    first_name = serializers.CharField(
        max_length=30,
        error_messages={
            "blank": _("Este campo não pode ficar em branco."),
            "required": _("Este campo é obrigatório."),
        },
    )
    last_name = serializers.CharField(
        max_length=150,
        error_messages={
            "blank": _("Este campo não pode ficar em branco."),
            "required": _("Este campo é obrigatório."),
        },
    )
    password = serializers.CharField(
        write_only=True,
        min_length=6,
        error_messages={
            "min_length": _("A senha precisa ter ao menos 6 caracteres."),
            "blank": _("Este campo não pode ficar em branco."),
            "required": _("Este campo é obrigatório."),
        },
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        allow_blank=True,
        min_length=6,
        error_messages={
            "min_length": _("A senha precisa ter ao menos 6 caracteres."),
            "blank": _("Este campo não pode ficar em branco."),
            "required": _("Este campo é obrigatório."),
        },
    )

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        if data.get("password") != data.get("password_confirm"):
            raise serializers.ValidationError({"password_confirm": [_("As senhas não coincidem.")]})
        return data

    def create_dto(self) -> RegisterDTO:
        return RegisterDTO(
            username=self.validated_data.get("username"),
            password=self.validated_data.get("password"),
            first_name=self.validated_data.get("first_name"),
            last_name=self.validated_data.get("last_name"),
        )


class LoginSerializer(serializers.Serializer[Any]):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True)


class GoogleLoginSerializer(serializers.Serializer[Any]):
    id_token = serializers.CharField()


class RefreshSerializer(serializers.Serializer[Any]):
    refresh = serializers.CharField()


class TokenSerializer(serializers.Serializer[Any]):
    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)


class ProfileSerializer(serializers.ModelSerializer[Profile]):
    """Profile plus the caller's panel roles and levels. The view passes an ``AccessGrantsDTO``
    as ``context["access_grants"]``; shapes in
    specs/012-feature-role-permissions/contracts/profile-api.md.
    """

    photo_url = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    # Set only in the Django admin; a value sent in PATCH is ignored (spec 015 FR-003).
    member_id = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = Profile
        fields = ["name", "is_member", "photo_url", "roles", "permissions", "member_id"]
        read_only_fields = ["is_member", "photo_url", "roles", "permissions", "member_id"]

    def _access_grants(self) -> AccessGrantsDTO:
        # No silent default: a view that forgot to pass the grants would tell the app the user
        # has no role, hiding the panel from an administrator.
        grants = self.context.get("access_grants")
        if not isinstance(grants, AccessGrantsDTO):
            raise KeyError(
                f"ProfileSerializer needs context['access_grants'] as AccessGrantsDTO, "
                f"got {type(grants).__name__}."
            )
        return grants

    def get_roles(self, obj: Profile) -> list[dict[str, str]]:
        """>>> serializer.get_roles(profile)
        [{'id': 'leader', 'name': 'Liderança'}]
        """
        return [
            {"id": role.value, "name": ROLE_DISPLAY_NAMES[role]}
            for role in self._access_grants().roles
        ]

    def get_permissions(self, obj: Profile) -> dict[str, str | None]:
        """Every scope as a key, so the app never has to guess a missing one.

        >>> serializer.get_permissions(profile)["members"]
        'manage'
        """
        grants = self._access_grants()
        return {
            scope.value: level.wire_name if (level := grants.level_for(scope)) else None
            for scope in Scope
        }

    def get_photo_url(self, obj: Profile) -> str | None:
        request: Request | None = self.context.get("request")
        if obj.photo and request:
            return request.build_absolute_uri(obj.photo.url)
        return None
