"""E-mail delivery (specs/028-password-recovery FR-020): out of the request, and a failure never
puts the address in a log."""

import logging
import smtplib
import threading
from collections.abc import Callable

import pytest
from django.core import mail

from features.accounts.dtos import EmailMessageDTO
from features.accounts.repositories.email_sender import BackgroundEmailSender, SmtpEmailSender
from features.accounts.tests.fakes import FailingEmailSender, RecordingEmailSender

ADDRESS = "ana@example.com"
MESSAGE = EmailMessageDTO(to=ADDRESS, subject="Assunto", body="ana: 123456")


def _run_inline(work: Callable[[], None]) -> None:
    work()


def _refuse_thread(work: Callable[[], None]) -> None:
    raise RuntimeError("can't start new thread")


def test_smtp_sender_goes_through_the_configured_backend() -> None:
    SmtpEmailSender().send(MESSAGE)

    assert mail.outbox[0].to == [ADDRESS]
    assert mail.outbox[0].subject == "Assunto"
    assert mail.outbox[0].body == "ana: 123456"


def test_background_sender_delivers_in_another_thread() -> None:
    threads: list[threading.Thread] = []
    delivered = threading.Event()

    class ThreadRecordingSender(RecordingEmailSender):
        def send(self, message: EmailMessageDTO) -> None:
            threads.append(threading.current_thread())
            delivered.set()

    BackgroundEmailSender(ThreadRecordingSender()).send(MESSAGE)

    assert delivered.wait(timeout=5)
    assert threads[0] is not threading.current_thread()
    assert threads[0].daemon


def test_background_sender_hands_over_the_message() -> None:
    delivery = RecordingEmailSender()

    BackgroundEmailSender(delivery, start_thread=_run_inline).send(MESSAGE)

    assert delivery.messages == [MESSAGE]


def test_delivery_failure_is_logged_without_address_or_code(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # The real failure: smtplib puts the refused address in the exception's args.
    failure = smtplib.SMTPRecipientsRefused({ADDRESS: (550, b"no such user")})
    sender = BackgroundEmailSender(FailingEmailSender(failure), start_thread=_run_inline)

    with caplog.at_level(logging.ERROR):
        sender.send(MESSAGE)

    record = caplog.records[0]
    assert record.getMessage() == "email_delivery_failed"
    assert record.error_type == "SMTPRecipientsRefused"  # type: ignore[attr-defined]
    assert record.exc_info is None
    assert ADDRESS not in caplog.text
    assert "123456" not in caplog.text


def test_a_thread_that_cannot_start_does_not_fail_the_request(
    caplog: pytest.LogCaptureFixture,
) -> None:
    sender = BackgroundEmailSender(RecordingEmailSender(), start_thread=_refuse_thread)

    with caplog.at_level(logging.ERROR):
        sender.send(MESSAGE)

    assert caplog.records[0].getMessage() == "email_delivery_failed"
