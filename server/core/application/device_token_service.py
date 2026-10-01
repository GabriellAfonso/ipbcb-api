from uuid import UUID

from core.domain.exceptions import ValidationError
from core.models.device_token import TOKEN_MAX_LENGTH
from core.repositories.interfaces import DeviceTokenRepository


class DeviceTokenService:
    """Register and forget the push token of the caller's device (specs/017-sunday-setlist-push
    R-14). The app registers after every login and token rotation, and forgets on logout."""

    def __init__(self, token_repository: DeviceTokenRepository) -> None:
        self._tokens = token_repository

    def register(self, user_id: UUID, raw_token: object) -> None:
        """>>> service.register(ana.pk, "fcm-token")"""
        self._tokens.register(user_id, valid_token(raw_token))

    def unregister(self, user_id: UUID, raw_token: object) -> None:
        """Forget the token if the caller owns it; anything else is a silent no-op, so logout
        never fails on it.

        >>> service.unregister(ana.pk, "fcm-token")
        """
        self._tokens.unregister(user_id, valid_token(raw_token))


def valid_token(raw_token: object) -> str:
    """The token trimmed, or ``ValidationError`` naming the expected shape. Never echoes the
    value: it is a credential to the device.

    >>> valid_token("  fcm-token ")
    'fcm-token'
    """
    if not isinstance(raw_token, str):
        raise ValidationError(f"Field 'token' must be a string, got {type(raw_token).__name__}.")
    token = raw_token.strip()
    if not 1 <= len(token) <= TOKEN_MAX_LENGTH or any(c.isspace() for c in token):
        raise ValidationError(
            f"Field 'token' must be 1 to {TOKEN_MAX_LENGTH} characters without spaces, "
            f"got {len(token)} characters."
        )
    return token
