"""Builds the push sender from the configured credentials (specs/017-sunday-setlist-push R-06).

Errors name what is wrong — the variable, the missing key — and never echo the value: it holds
a private key.
"""

import base64
import binascii
import json

from django.core.exceptions import ImproperlyConfigured
from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account

from core.push.disabled_sender import DisabledPushSender
from core.push.fcm_sender import FCM_SCOPE, FcmPushSender
from core.push.sender import PushSender

CREDENTIALS_SETTING = "FCM_SERVICE_ACCOUNT_JSON_BASE64"
_REQUIRED_KEYS = ("project_id", "client_email", "private_key")


def build_push_sender(encoded_credentials: str) -> PushSender:
    """``DisabledPushSender`` when nothing is configured, else an FCM sender.

    >>> build_push_sender("")
    <core.push.disabled_sender.DisabledPushSender object at ...>
    """
    if not encoded_credentials.strip():
        return DisabledPushSender()
    info = decode_service_account(encoded_credentials)
    # google-auth ships no type hints, same as in GoogleAuthService.
    credentials = service_account.Credentials.from_service_account_info(  # type: ignore[no-untyped-call]
        info, scopes=[FCM_SCOPE]
    )
    session = AuthorizedSession(credentials)  # type: ignore[no-untyped-call]
    return FcmPushSender(session, project_id=info["project_id"])


def decode_service_account(encoded_credentials: str) -> dict[str, str]:
    """Base64 line -> service account dict, with the keys the sender needs checked.

    >>> decode_service_account(base64.b64encode(b'{"project_id": "p", ...}').decode())["project_id"]
    'p'
    """
    try:
        raw = base64.b64decode(encoded_credentials.strip(), validate=True)
        info = json.loads(raw)
    except (binascii.Error, ValueError) as exc:
        raise ImproperlyConfigured(
            f"{CREDENTIALS_SETTING} must be a base64-encoded service account JSON "
            f"(decode failed: {type(exc).__name__})."
        ) from None
    if not isinstance(info, dict):
        raise ImproperlyConfigured(f"{CREDENTIALS_SETTING} must decode to a JSON object.")
    missing = [key for key in _REQUIRED_KEYS if not info.get(key)]
    if missing:
        raise ImproperlyConfigured(
            f"{CREDENTIALS_SETTING} is missing service account keys: {missing}; "
            f"expected {list(_REQUIRED_KEYS)}."
        )
    return info
