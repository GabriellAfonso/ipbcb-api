import logging
import threading
from collections.abc import Callable

from django.core.mail import EmailMessage

from features.accounts.dtos import EmailMessageDTO
from features.accounts.repositories.interfaces import EmailSender

logger = logging.getLogger(__name__)

ThreadStarter = Callable[[Callable[[], None]], None]


def _start_daemon_thread(work: Callable[[], None]) -> None:
    # Daemon: it must not hold a worker's graceful shutdown. A message lost on restart is the
    # accepted cost (specs/028-password-recovery research R-06).
    threading.Thread(target=work, daemon=True).start()


class SmtpEmailSender(EmailSender):
    """Delivers through the backend in settings. Blocks until the server answers, up to
    ``EMAIL_TIMEOUT``, and raises on failure."""

    def send(self, message: EmailMessageDTO) -> None:
        """>>> SmtpEmailSender().send(EmailMessageDTO(to="a@b.com", subject="s", body="b"))"""
        EmailMessage(subject=message.subject, body=message.body, to=[message.to]).send()


class BackgroundEmailSender(EmailSender):
    """Hands delivery to a thread, so the request never waits for the provider: the response time
    would reveal which addresses have accounts (FR-020).

    The message is fully built by then, so the thread never touches the database. A failure is
    logged by exception type only: ``SMTPRecipientsRefused`` carries the address in its text and
    args, so neither the message nor ``exc_info`` may reach the log.
    """

    def __init__(
        self, delivery: EmailSender, start_thread: ThreadStarter = _start_daemon_thread
    ) -> None:
        self._delivery = delivery
        self._start_thread = start_thread

    def send(self, message: EmailMessageDTO) -> None:
        """>>> BackgroundEmailSender(SmtpEmailSender()).send(message)"""
        try:
            self._start_thread(lambda: self._deliver(message))
        except RuntimeError as exc:
            # Runs in on_commit: the data is saved, so the request must still get its answer.
            self._log_failure(exc)

    def _deliver(self, message: EmailMessageDTO) -> None:
        try:
            self._delivery.send(message)
        except Exception as exc:  # A thread has nobody above it to report to.
            self._log_failure(exc)

    def _log_failure(self, exc: Exception) -> None:
        logger.error("email_delivery_failed", extra={"error_type": type(exc).__name__})
