from rest_framework import serializers
from apps.persistence.models.songs import Song, Played
from apps.persistence.models.profile import User
from django.utils.translation import gettext_lazy as _
from apps.persistence.models.profile import Profile


class SongSerializer(serializers.ModelSerializer):
    class Meta:
        model = Song
        fields = ['id', 'title', 'artist']


class PlayedSerializer(serializers.ModelSerializer):
    song = SongSerializer(read_only=True)
    date = serializers.DateField(format="%d/%m/%Y")

    class Meta:
        model = Played
        fields = ['id', 'song', 'date', 'tone', 'position']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        min_length=6,
        error_messages={
            "min_length": _("A senha precisa ter ao menos 6 caracteres."),
            "blank": _("Este campo não pode ficar em branco."),
            "required": _("Este campo é obrigatório."),
        },
    )

    # Mantém o nome que você quer retornar no erro (password_confirm)
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

    first_name = serializers.CharField(
        max_length=30,
        error_messages={"blank": _("Este campo não pode ficar em branco."), "required": _(
            "Este campo é obrigatório.")},
    )
    last_name = serializers.CharField(
        max_length=150,
        error_messages={"blank": _("Este campo não pode ficar em branco."), "required": _(
            "Este campo é obrigatório.")},
    )

    class Meta:
        model = User
        fields = ["username", "first_name",
                  "last_name", "password", "password_confirm"]
        extra_kwargs = {
            "username": {
                "error_messages": {
                    "blank": _("Este campo não pode ficar em branco."),
                    "required": _("Este campo é obrigatório."),
                }
            }
        }

    def validate(self, data):
        password = data.get("password")

        password_confirm = data.get("password_confirm")

        if password != password_confirm:
            raise serializers.ValidationError(
                {"password_confirm": [_("As senhas não coincidem.")]})

        # garante que o fluxo abaixo use o campo correto
        data["password_confirm"] = password_confirm
        return data

    def create(self, validated_data):
        validated_data.pop("password_confirm", None)
        password = validated_data.pop("password")
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user


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
