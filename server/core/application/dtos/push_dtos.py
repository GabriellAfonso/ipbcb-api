from datetime import date

from pydantic import ConfigDict

from core.application.dtos.strict_base import StrictBaseModel
from core.domain.push import PushMessageType


class PushMessage(StrictBaseModel):
    """One data message: what happened and for which Sunday. Carries nothing else — no song,
    member or user data (spec 017 FR-011).

    >>> PushMessage(type=PushMessageType.SETLIST_SAVED, date=date(2026, 10, 4)).as_data()
    {'type': 'setlist_saved', 'date': '2026-10-04'}
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: PushMessageType
    date: date

    def as_data(self) -> dict[str, str]:
        """The FCM ``data`` payload, whose values must all be strings."""
        return {"type": self.type.value, "date": self.date.isoformat()}


class PushSendReport(StrictBaseModel):
    """What one sender call did with its tokens. ``aborted`` means a transport failure stopped
    the batch; the tokens not tried are counted in ``failed``. ``disabled`` means no credentials.

    >>> PushSendReport(sent=2, failed=0, invalid_tokens=["t3"], aborted=False, disabled=False)
    """

    sent: int = 0
    failed: int = 0
    invalid_tokens: list[str] = []
    aborted: bool = False
    disabled: bool = False


class PushOutcome(StrictBaseModel):
    """What ``PushService.notify`` did, as logged. Counts only — never a token.

    >>> PushOutcome(recipients=3, devices=4, sent=4)
    """

    recipients: int = 0
    devices: int = 0
    sent: int = 0
    failed: int = 0
    invalid_removed: int = 0
    aborted: bool = False
    disabled: bool = False
