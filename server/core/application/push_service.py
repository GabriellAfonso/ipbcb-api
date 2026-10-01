import logging
from collections.abc import Collection
from uuid import UUID

from core.application.dtos.push_dtos import PushMessage, PushOutcome, PushSendReport
from core.metrics import PUSH_MESSAGES_COUNTER
from core.push.sender import PushSender
from core.repositories.interfaces import DeviceTokenRepository

logger = logging.getLogger(__name__)


class PushService:
    """Sends one message to every device of some users, and forgets the devices the provider
    says are gone (specs/017-sunday-setlist-push R-05, R-07).

    Never raises: callers send after their own work has committed, and a push failure must not
    turn a saved setlist into an error. Logs carry counts and ids only — never a token.
    """

    def __init__(self, token_repository: DeviceTokenRepository, sender: PushSender) -> None:
        self._tokens = token_repository
        self._sender = sender

    def notify(self, user_ids: Collection[UUID], message: PushMessage) -> PushOutcome:
        """>>> service.notify({ana.pk}, PushMessage(type=PushMessageType.SETLIST_SAVED, date=d))
        PushOutcome(recipients=1, devices=2, sent=2, ...)
        """
        tokens = self._tokens.tokens_for(user_ids) if user_ids else []
        if not tokens:
            return self._finish(message, PushOutcome(recipients=len(user_ids)))
        report = self._send(tokens, message)
        removed = self._tokens.delete_tokens(report.invalid_tokens) if report.invalid_tokens else 0
        return self._finish(message, _outcome(len(user_ids), len(tokens), report, removed))

    def _send(self, tokens: list[str], message: PushMessage) -> PushSendReport:
        try:
            return self._sender.send(tokens, message)
        except Exception as exc:  # a sender bug must never fail the caller
            logger.exception(
                "push_transport_error",
                extra={"push_type": message.type.value, "error_class": type(exc).__name__},
            )
            return PushSendReport(failed=len(tokens), aborted=True)

    def _finish(self, message: PushMessage, outcome: PushOutcome) -> PushOutcome:
        fields = {"push_type": message.type.value, "push_date": message.date.isoformat()}
        if outcome.disabled:
            logger.warning("push_disabled", extra={**fields, "devices": outcome.devices})
            return outcome
        # Warning when anything was lost, so a dead provider shows up next to the saves it hit.
        level = logging.WARNING if outcome.aborted or outcome.failed else logging.INFO
        logger.log(level, "push_sent", extra={**fields, **outcome.model_dump()})
        _count(message, outcome)
        return outcome


def _outcome(recipients: int, devices: int, report: PushSendReport, removed: int) -> PushOutcome:
    return PushOutcome(
        recipients=recipients,
        devices=devices,
        sent=report.sent,
        failed=report.failed,
        invalid_removed=removed,
        aborted=report.aborted,
        disabled=report.disabled,
    )


def _count(message: PushMessage, outcome: PushOutcome) -> None:
    for name, value in (
        ("sent", outcome.sent),
        ("failed", outcome.failed),
        ("invalid", outcome.invalid_removed),
    ):
        if value:
            PUSH_MESSAGES_COUNTER.labels(type=message.type.value, outcome=name).inc(value)
