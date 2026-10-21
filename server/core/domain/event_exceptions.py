"""Church events domain exceptions (specs/020-church-events).

Their own module, like ``gallery_exceptions``, to keep ``core/domain/exceptions.py`` under 500
lines; that module re-exports every name here. Validation messages are in Portuguese: they reach
the app screen through ``field_errors``, keyed by the form field the app highlights.
"""

from collections.abc import Collection
from datetime import date

from core.domain.base_exceptions import NotFoundError, ValidationError


class EventNotFoundError(NotFoundError):
    """No event with this id — or one the caller may not see (a past event on the public detail,
    a members event for a non-member). Same message either way, so nothing leaks.

    >>> raise EventNotFoundError(12)
    """

    def __init__(self, event_id: int) -> None:
        super().__init__(f"Evento não encontrado: id={event_id}.")
        self.event_id = event_id


class _FieldValidationError(ValidationError):
    """A validation error that belongs to one form field."""

    field_name: str = ""

    def extra_context(self) -> dict[str, object]:
        return {"field_errors": {self.field_name: [str(self)]}}


class EventImageInvalidError(_FieldValidationError):
    """The uploaded image breaks a rule (format, size, pixels, minimum size, ratio).

    >>> raise EventImageInvalidError("Proporção 1.60; esperado 16:9 (1.78) com tolerância de 2%.")
    """

    field_name = "image"

    def __init__(self, reason: str) -> None:
        super().__init__(reason)


class EventImageMissingError(_FieldValidationError):
    """Creating an event without an image.

    >>> raise EventImageMissingError()
    """

    field_name = "image"

    def __init__(self) -> None:
        super().__init__("Envie a imagem do evento no campo 'image' (16:9, JPEG, PNG ou WEBP).")


class EventDatesInvalidError(_FieldValidationError):
    """``end_date`` before ``start_date`` on the resulting event.

    >>> raise EventDatesInvalidError(date(2026, 11, 10), date(2026, 11, 8))
    """

    field_name = "end_date"

    def __init__(self, start_date: date, end_date: date) -> None:
        super().__init__(
            f"Data de término {end_date.isoformat()} é anterior à data de início "
            f"{start_date.isoformat()}; esperado uma data igual ou posterior."
        )


class EventStatusFilterError(_FieldValidationError):
    """Unknown ``status`` filter on the management list.

    >>> raise EventStatusFilterError("old", ["active", "past", "all"])
    """

    field_name = "status"

    def __init__(self, value: str, accepted: Collection[str]) -> None:
        super().__init__(f"Filtro 'status' inválido: {value!r}. Use um de: {', '.join(accepted)}.")
