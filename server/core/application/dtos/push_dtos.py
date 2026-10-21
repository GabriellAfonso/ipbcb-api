import datetime as dt

from pydantic import ConfigDict

from core.application.dtos.strict_base import StrictBaseModel
from core.domain.push import PushMessageType


class PushMessage(StrictBaseModel):
    """One data message: what happened and what it is about — a Sunday (``date``) or an access
    request (``request_id``, ``request_type``). Carries no song, member or user data (spec 017
    FR-011). The one free text is a denial ``reason``, written by a leader to the person who
    receives it (specs/022-access-requests R-05). Only the fields set reach the payload.

    >>> PushMessage(type=PushMessageType.SETLIST_SAVED, date=dt.date(2026, 10, 4)).as_data()
    {'type': 'setlist_saved', 'date': '2026-10-04'}
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: PushMessageType
    # Module-qualified: a field named "date" with a None default shadows the type in the class
    # namespace while pydantic evaluates the annotation.
    date: dt.date | None = None
    request_id: int | None = None
    request_type: str | None = None
    reason: str | None = None

    def as_data(self) -> dict[str, str]:
        """The FCM ``data`` payload, whose values must all be strings."""
        data = {"type": self.type.value}
        if self.date is not None:
            data["date"] = self.date.isoformat()
        for key in ("request_id", "request_type", "reason"):
            value = getattr(self, key)
            if value is not None:
                data[key] = str(value)
        return data


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
