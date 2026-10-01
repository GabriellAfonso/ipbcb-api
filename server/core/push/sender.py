from collections.abc import Sequence
from typing import Protocol

from core.application.dtos.push_dtos import PushMessage, PushSendReport


class PushSender(Protocol):
    """Delivers one message to each token. Never raises for a per-token failure; reports it."""

    def send(self, tokens: Sequence[str], message: PushMessage) -> PushSendReport: ...
