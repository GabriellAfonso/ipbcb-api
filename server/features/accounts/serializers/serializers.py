from typing import Any, TypedDict

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from features.accounts.models.profile import Profile
from features.accounts.models.user import User
from features.core.application.dtos.auth_dtos import RegisterDTO


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
        normalized = value.strip().lower()
        if User.objects.filter(username=normalized).exists():
            raise serializers.ValidationError(_("Este nome de usuário já está em uso."))
        return value
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
            raise serializers.ValidationError({
                "password_confirm": [_("As senhas não coincidem.")]
            })
        return data

    def create_dto(self) -> RegisterDTO:
        return RegisterDTO(
            username=self.validated_data.get("username"),
            password=self.validated_data.get("password"),
            first_name=self.validated_data.get("first_name"),
            last_name=self.validated_data.get("last_name"),
        )


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True)


class GoogleLoginSerializer(serializers.Serializer):
    id_token = serializers.CharField()


class TokenSerializer(serializers.Serializer):
    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)


class ProfilePhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ["photo"]

    def update(self, instance, validated_data):
        if instance.photo and "photo" in validated_data:
            instance.photo.delete(save=False)
        return super().update(instance, validated_data)


class ProfileSerializer(serializers.ModelSerializer):
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = ["name", "active", "is_admin", "is_member", "photo_url"]
        read_only_fields = ["active", "is_admin", "is_member", "photo_url"]

    def get_photo_url(self, obj):
        request = self.context.get("request")
        if obj.photo and request:
            return request.build_absolute_uri(obj.photo.url)
        return None
