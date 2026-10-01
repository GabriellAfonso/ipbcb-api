"""Worship setlist domain exceptions (specs/017-sunday-setlist-push).

Their own module, like ``gallery_exceptions``, to keep ``core/domain/exceptions.py`` under 500
lines; that module re-exports every name here.
"""

from collections.abc import Collection
from datetime import date

from core.domain.base_exceptions import NotFoundError, PermissionDeniedError, ValidationError

_WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


class NotWorshipMemberError(PermissionDeniedError):
    """The caller is not in the worship ministry. Portuguese: the app shows it as is.

    >>> raise NotWorshipMemberError()
    """

    def __init__(self) -> None:
        super().__init__("Disponível apenas para o ministério de Louvor.")


class SetlistDateNotSundayError(ValidationError):
    """A setlist date that is not a Sunday.

    >>> raise SetlistDateNotSundayError(date(2026, 10, 5))
    """

    def __init__(self, day: date) -> None:
        weekday = _WEEKDAY_NAMES[day.weekday()]
        super().__init__(f"Setlist date must be a Sunday; got {day.isoformat()} ({weekday}).")
        self.day = day

    def extra_context(self) -> dict[str, object]:
        return {"date": self.day.isoformat()}


class DuplicateSetlistPositionError(ValidationError):
    """Two or more items share a position.

    >>> raise DuplicateSetlistPositionError([2, 3])
    """

    def __init__(self, positions: Collection[int]) -> None:
        repeated = sorted(positions)
        super().__init__(f"Setlist positions must be unique; repeated: {repeated}.")
        self.positions = repeated

    def extra_context(self) -> dict[str, object]:
        return {"positions": self.positions}


class SetlistNotFoundError(NotFoundError):
    """No setlist saved for this date.

    >>> raise SetlistNotFoundError(date(2026, 10, 4))
    """

    def __init__(self, day: date) -> None:
        super().__init__(f"Setlist not found: date={day.isoformat()}")
        self.day = day

    def extra_context(self) -> dict[str, object]:
        return {"date": self.day.isoformat()}
