from datetime import date
from unittest.mock import MagicMock

import pytest

from core.domain.exceptions import (
    DomainError,
    EventDatesInvalidError,
    EventImageInvalidError,
    EventImageMissingError,
    EventNotFoundError,
    EventStatusFilterError,
)
from core.http.exceptions import custom_exception_handler


def _handle(exc: DomainError) -> tuple[int, dict[str, object]]:
    response = custom_exception_handler(exc, {"request": MagicMock(), "view": MagicMock()})
    assert response is not None
    return response.status_code, dict(response.data)


def test_not_found_is_404_naming_the_id() -> None:
    status, body = _handle(EventNotFoundError(12))

    assert status == 404
    assert body["error_code"] == "NOT_FOUND"
    assert "id=12" in str(body["detail"])
    assert "field_errors" not in body


@pytest.mark.parametrize(
    ("exc", "field"),
    [
        (EventImageInvalidError("Proporção 1.60; esperado 16:9."), "image"),
        (EventImageMissingError(), "image"),
        (EventDatesInvalidError(date(2026, 11, 10), date(2026, 11, 8)), "end_date"),
        (EventStatusFilterError("old", ["active", "past", "all"]), "status"),
    ],
)
def test_validation_errors_are_400_on_their_field(exc: DomainError, field: str) -> None:
    status, body = _handle(exc)

    assert status == 400
    assert body["error_code"] == "VALIDATION_ERROR"
    assert body["field_errors"] == {field: [str(exc)]}


def test_dates_message_names_both_dates() -> None:
    message = str(EventDatesInvalidError(date(2026, 11, 10), date(2026, 11, 8)))

    assert "2026-11-08" in message and "2026-11-10" in message


def test_status_message_names_value_and_accepted_ones() -> None:
    message = str(EventStatusFilterError("old", ["active", "past", "all"]))

    assert "'old'" in message and "active, past, all" in message
