"""Input of the account-deletion web page (specs/021-user-account FR-016). DRF serializers on a
plain Django view: every input reaching the database goes through one (constitution)."""

from typing import Any

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

CONFIRM_REQUIRED_MESSAGE = _("Marque a caixa confirmando que quer excluir a conta.")
_REQUIRED = {
    "blank": _("Preencha todos os campos."),
    "required": _("Preencha todos os campos."),
}


class _ConfirmedDeletionSerializer(serializers.Serializer[Any]):
    # An unticked checkbox is simply absent from the form; DRF reads that as False.
    confirm = serializers.BooleanField()

    def validate_confirm(self, value: bool) -> bool:
        if not value:
            raise serializers.ValidationError(CONFIRM_REQUIRED_MESSAGE)
        return value


class WebPasswordDeletionSerializer(_ConfirmedDeletionSerializer):
    """``method=password``: the person signs in on the page itself."""

    username = serializers.CharField(max_length=150, error_messages={**_REQUIRED})
    password = serializers.CharField(trim_whitespace=False, error_messages={**_REQUIRED})


class WebGoogleDeletionSerializer(_ConfirmedDeletionSerializer):
    """``method=google``: ``credential`` is the ID token the Google button hands the page."""

    credential = serializers.CharField(
        error_messages={
            "blank": _("Entre com o Google antes de confirmar."),
            "required": _("Entre com o Google antes de confirmar."),
        }
    )


def first_error(serializer: serializers.Serializer[Any]) -> str:
    """The message the page shows for an invalid form: one line, the first problem.

    >>> first_error(WebGoogleDeletionSerializer(data={"confirm": "on"}))
    'Entre com o Google antes de confirmar.'
    """
    for messages in serializer.errors.values():
        return str(messages[0])
    return str(_REQUIRED["required"])
