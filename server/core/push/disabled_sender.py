from collections.abc import Sequence

from core.application.dtos.push_dtos import PushMessage, PushSendReport


class DisabledPushSender:
    """Used when no push credentials are configured (development, or a production
    misconfiguration): sends nothing and says so, so the caller logs ``push_disabled``.

    >>> DisabledPushSender().send(["t1"], message).disabled
    True
    """

    def send(self, tokens: Sequence[str], message: PushMessage) -> PushSendReport:
        return PushSendReport(disabled=True)
