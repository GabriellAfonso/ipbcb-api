from uuid import uuid4

import pytest

from core.application.device_token_service import DeviceTokenService
from core.domain.exceptions import ValidationError
from core.tests.fakes import FakeDeviceTokenRepository

ANA, BIA = uuid4(), uuid4()


def _service() -> tuple[DeviceTokenService, FakeDeviceTokenRepository]:
    tokens = FakeDeviceTokenRepository()
    return DeviceTokenService(tokens), tokens


def test_register_stores_trimmed_token() -> None:
    service, tokens = _service()
    service.register(ANA, "  fcm-token\n")
    assert tokens.owners == {"fcm-token": ANA}


@pytest.mark.parametrize("raw", [None, 12, "", "   ", "has space", "x" * 513])
def test_bad_tokens_are_refused(raw: object) -> None:
    service, tokens = _service()
    with pytest.raises(ValidationError, match="'token'"):
        service.register(ANA, raw)
    assert tokens.owners == {}


def test_error_never_echoes_the_token() -> None:
    with pytest.raises(ValidationError) as error:
        _service()[0].register(ANA, "secret value")
    assert "secret" not in str(error.value)


def test_max_length_is_accepted() -> None:
    service, tokens = _service()
    service.register(ANA, "x" * 512)
    assert len(tokens.owners) == 1


def test_unregister_only_own_token() -> None:
    service, tokens = _service()
    service.register(ANA, "t1")
    service.unregister(BIA, "t1")
    assert tokens.owners == {"t1": ANA}
    service.unregister(ANA, "t1")
    assert tokens.owners == {}
