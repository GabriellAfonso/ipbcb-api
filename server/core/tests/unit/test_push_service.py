from datetime import date
from uuid import UUID, uuid4

import pytest

from core.application.dtos.push_dtos import PushMessage, PushSendReport
from core.application.push_service import PushService
from core.domain.push import PushMessageType
from core.tests.fakes import FakeDeviceTokenRepository, FakePushSender

ANA, BIA = uuid4(), uuid4()
MESSAGE = PushMessage(type=PushMessageType.SETLIST_SAVED, date=date(2026, 10, 4))


def _service(
    sender: FakePushSender, owners: dict[str, UUID] | None = None
) -> tuple[PushService, FakeDeviceTokenRepository]:
    default = {"a1": ANA, "a2": ANA, "b1": BIA}
    tokens = FakeDeviceTokenRepository(default if owners is None else owners)
    return PushService(tokens, sender), tokens


def test_no_recipients_sends_nothing() -> None:
    sender = FakePushSender()
    outcome = _service(sender)[0].notify(set(), MESSAGE)
    assert sender.calls == [] and outcome.devices == 0


def test_recipients_without_devices_send_nothing() -> None:
    sender = FakePushSender()
    outcome = _service(sender, owners={})[0].notify({ANA}, MESSAGE)
    assert sender.calls == [] and outcome.recipients == 1 and outcome.devices == 0


def test_sends_to_every_device_of_the_recipients() -> None:
    sender = FakePushSender()
    outcome = _service(sender)[0].notify({ANA}, MESSAGE)
    assert sender.calls == [(["a1", "a2"], MESSAGE)]
    assert outcome.sent == 2 and outcome.devices == 2


def test_invalid_tokens_are_deleted() -> None:
    service, tokens = _service(FakePushSender(invalid={"a2"}))
    outcome = service.notify({ANA, BIA}, MESSAGE)
    assert outcome.invalid_removed == 1
    assert "a2" not in tokens.owners and "a1" in tokens.owners


def test_sender_exception_never_escapes(caplog: pytest.LogCaptureFixture) -> None:
    service, _ = _service(FakePushSender(raises=RuntimeError("boom")))
    outcome = service.notify({ANA}, MESSAGE)
    assert outcome.aborted and outcome.failed == 2
    assert "push_transport_error" in [r.getMessage() for r in caplog.records]


def test_abort_is_logged_as_warning(caplog: pytest.LogCaptureFixture) -> None:
    report = PushSendReport(sent=1, failed=1, aborted=True)
    with caplog.at_level("INFO"):
        _service(FakePushSender(report=report))[0].notify({ANA}, MESSAGE)
    record = next(r for r in caplog.records if r.getMessage() == "push_sent")
    assert record.levelname == "WARNING" and getattr(record, "aborted") is True


def test_disabled_is_logged_as_warning(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("INFO"):
        outcome = _service(FakePushSender(report=PushSendReport(disabled=True)))[0].notify(
            {ANA}, MESSAGE
        )
    assert outcome.disabled
    assert [(r.getMessage(), r.levelname) for r in caplog.records] == [("push_disabled", "WARNING")]


def test_logs_never_carry_a_token(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("DEBUG"):
        _service(FakePushSender(invalid={"a2"}))[0].notify({ANA}, MESSAGE)
    for record in caplog.records:
        assert "a1" not in str(record.__dict__.values())
        assert "a2" not in str(record.__dict__.values())
