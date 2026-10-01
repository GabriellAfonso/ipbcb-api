import base64
import json

import pytest
from django.core.exceptions import ImproperlyConfigured

from core.push.disabled_sender import DisabledPushSender
from core.push.factory import build_push_sender, decode_service_account

SECRET = "-----BEGIN PRIVATE KEY-----secret"


def _encode(info: object) -> str:
    return base64.b64encode(json.dumps(info).encode()).decode()


def test_empty_means_disabled() -> None:
    assert isinstance(build_push_sender(""), DisabledPushSender)
    assert isinstance(build_push_sender("   "), DisabledPushSender)


def test_decodes_service_account() -> None:
    info = {"project_id": "p", "client_email": "a@p.iam", "private_key": SECRET}
    assert decode_service_account(_encode(info)) == info


def test_not_base64_is_refused_without_echoing() -> None:
    with pytest.raises(ImproperlyConfigured) as error:
        decode_service_account("not base64 !!" + SECRET)
    assert "FCM_SERVICE_ACCOUNT_JSON_BASE64" in str(error.value)
    assert SECRET not in str(error.value)


def test_not_an_object_is_refused() -> None:
    with pytest.raises(ImproperlyConfigured, match="JSON object"):
        decode_service_account(_encode(["x"]))


def test_missing_keys_are_named_not_the_value() -> None:
    with pytest.raises(ImproperlyConfigured) as error:
        decode_service_account(_encode({"project_id": "p", "private_key": SECRET}))
    assert "client_email" in str(error.value)
    assert SECRET not in str(error.value)
