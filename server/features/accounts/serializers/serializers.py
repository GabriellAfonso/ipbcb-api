from typing import Any, TypedDict
from zoneinfo import ZoneInfo

from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.request import Request

from features.accounts.models.profile import Profile
from features.accounts.validators import USERNAME_RULE_MESSAGE, is_valid_username
from features.accounts.models.user import User
from core.application.dtos.access_dtos import AccessGrantsDTO
from core.application.dtos.account_dtos import AccountDeletionDTO, PasswordChangeDTO
from core.application.dtos.auth_dtos import RegisterDTO
from core.application.dtos.worship_dtos import WorshipFlagsDTO
from core.domain.access import ROLE_DISPLAY_NAMES, Scope
from features.accounts.dtos import MemberAccessStateDTO


# Named, not taken from settings.TIME_ZONE: the contract fixes the zone of `date_joined`
# (specs/021-user-account), whatever the server runs in.
CHURCH_TIME_ZONE = ZoneInfo("America/Sao_Paulo")

_REQUIRED_MESSAGES = {
    "blank": _("Este campo não pode ficar em branco."),
    "required": _("Este campo é obrigatório."),
}
PASSWORDS_DIFFER_MESSAGE = _("As senhas não coincidem.")


def password_field(*, allow_blank: bool = False) -> serializers.CharField:
    """The password rule of registration and password change: at least 6 characters, nothing
    else (constitution: no complexity validators). One definition so the two cannot drift.

    >>> password_field().min_length
    6
    """
    return serializers.CharField(
        write_only=True,
        min_length=6,
        allow_blank=allow_blank,
        error_messages={
            "min_length": _("A senha precisa ter ao menos 6 caracteres."),
            **_REQUIRED_MESSAGES,
        },
    )


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
    password = password_field()
    password_confirm = password_field(allow_blank=True)

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        if data.get("password") != data.get("password_confirm"):
            raise serializers.ValidationError({"password_confirm": [PASSWORDS_DIFFER_MESSAGE]})
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


class PasswordChangeSerializer(serializers.Serializer[Any]):
    """``POST api/me/password/`` (specs/021-user-account/contracts/account-api.md)."""

    # No length rule on the current password: it only has to match, and an old account may
    # predate the 6-character minimum.
    current_password = serializers.CharField(
        write_only=True, trim_whitespace=False, error_messages={**_REQUIRED_MESSAGES}
    )
    new_password = password_field()
    new_password_confirm = password_field(allow_blank=True)

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        if data.get("new_password") != data.get("new_password_confirm"):
            raise serializers.ValidationError({"new_password_confirm": [PASSWORDS_DIFFER_MESSAGE]})
        return data

    def create_dto(self) -> PasswordChangeDTO:
        return PasswordChangeDTO(
            current_password=self.validated_data["current_password"],
            new_password=self.validated_data["new_password"],
        )


class AccountDeletionSerializer(serializers.Serializer[Any]):
    """``POST api/me/delete/``. Both fields optional here: which one is required depends on the
    account, which only the service knows (research R-05)."""

    password = serializers.CharField(
        write_only=True, required=False, allow_blank=True, trim_whitespace=False
    )
    id_token = serializers.CharField(write_only=True, required=False, allow_blank=True)

    def create_dto(self) -> AccountDeletionDTO:
        return AccountDeletionDTO(
            password=self.validated_data.get("password") or None,
            id_token=self.validated_data.get("id_token") or None,
        )


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
    # Worship ministry flags (spec 017 US4), from ``context["worship_flags"]``.
    is_worship_member = serializers.SerializerMethodField()
    can_save_setlist = serializers.SerializerMethodField()
    # Account fields for the app's account screen (specs/021-user-account FR-001).
    username = serializers.CharField(source="user.username", read_only=True)
    has_password = serializers.SerializerMethodField()
    date_joined = serializers.SerializerMethodField()
    # Member access (specs/022-access-requests FR-004), from ``context["member_access_state"]``.
    # ``is_member`` is the old name of ``member_access``, kept with the same value for the app
    # versions that still read it.
    member_access = serializers.SerializerMethodField()
    is_member = serializers.SerializerMethodField()
    access_status = serializers.SerializerMethodField()
    data_correction_pending = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            "name",
            "is_member",
            "member_access",
            "access_status",
            "access_requests_blocked",
            "data_correction_pending",
            "photo_url",
            "roles",
            "permissions",
            "member_id",
            "is_worship_member",
            "can_save_setlist",
            "username",
            "has_password",
            "date_joined",
        ]
        read_only_fields = [
            "is_member",
            "member_access",
            "access_status",
            "access_requests_blocked",
            "data_correction_pending",
            "photo_url",
            "roles",
            "permissions",
            "member_id",
            "is_worship_member",
            "can_save_setlist",
            "username",
            "has_password",
            "date_joined",
        ]
        # The model allows a blank name (a profile is created before anyone names it); an edit
        # does not. DRF trims first, so a whitespace-only name is blank too.
        extra_kwargs = {
            "name": {
                "allow_blank": False,
                "error_messages": {
                    **_REQUIRED_MESSAGES,
                    "max_length": _("O nome pode ter no máximo 100 caracteres."),
                },
            }
        }

    def get_has_password(self, obj: Profile) -> bool:
        """The account's password, never the way it signed in: Google sign-in also enters an
        account that has one.

        >>> serializer.get_has_password(profile)
        True
        """
        return obj.user.has_usable_password()

    def get_date_joined(self, obj: Profile) -> str:
        """>>> serializer.get_date_joined(profile)
        '2025-03-14'
        """
        return localtime(obj.user.date_joined, CHURCH_TIME_ZONE).date().isoformat()

    def _member_access_state(self) -> MemberAccessStateDTO:
        # Same guard as _access_grants: a silent False would lock a leader out of every
        # member screen in the app without any error.
        state = self.context.get("member_access_state")
        if not isinstance(state, MemberAccessStateDTO):
            raise KeyError(
                f"ProfileSerializer needs context['member_access_state'] as MemberAccessStateDTO, "
                f"got {type(state).__name__}."
            )
        return state

    def get_member_access(self, obj: Profile) -> bool:
        """The effective access — flag or leadership role — not the stored flag.

        >>> serializer.get_member_access(leader_profile)
        True
        """
        return self._member_access_state().member_access

    def get_is_member(self, obj: Profile) -> bool:
        """>>> serializer.get_is_member(profile) == serializer.get_member_access(profile)
        True
        """
        return self._member_access_state().member_access

    def get_access_status(self, obj: Profile) -> str:
        """>>> serializer.get_access_status(profile)
        'pending'
        """
        return self._member_access_state().access_status.value

    def get_data_correction_pending(self, obj: Profile) -> bool:
        """>>> serializer.get_data_correction_pending(profile)
        False
        """
        return self._member_access_state().data_correction_pending

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

    def _worship_flags(self) -> WorshipFlagsDTO:
        # Same guard as _access_grants: a silent False would hide the setlist screens from the
        # worship leader without any error.
        flags = self.context.get("worship_flags")
        if not isinstance(flags, WorshipFlagsDTO):
            raise KeyError(
                f"ProfileSerializer needs context['worship_flags'] as WorshipFlagsDTO, "
                f"got {type(flags).__name__}."
            )
        return flags

    def get_is_worship_member(self, obj: Profile) -> bool:
        """>>> serializer.get_is_worship_member(profile)
        True
        """
        return self._worship_flags().is_worship_member

    def get_can_save_setlist(self, obj: Profile) -> bool:
        """>>> serializer.get_can_save_setlist(profile)
        False
        """
        return self._worship_flags().can_save_setlist

    def get_photo_url(self, obj: Profile) -> str | None:
        request: Request | None = self.context.get("request")
        if obj.photo and request:
            return request.build_absolute_uri(obj.photo.url)
        return None
