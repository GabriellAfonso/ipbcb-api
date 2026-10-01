from datetime import date

from core.domain.exceptions import (
    DuplicateSetlistPositionError,
    NotFoundError,
    NotWorshipMemberError,
    PermissionDeniedError,
    SetlistDateNotSundayError,
    SetlistNotFoundError,
    ValidationError,
)


def test_not_worship_member_is_a_403_in_portuguese() -> None:
    error = NotWorshipMemberError()
    assert isinstance(error, PermissionDeniedError)
    assert str(error) == "Disponível apenas para o ministério de Louvor."


def test_not_sunday_names_date_and_weekday() -> None:
    error = SetlistDateNotSundayError(date(2026, 10, 5))
    assert isinstance(error, ValidationError)
    assert "2026-10-05" in str(error) and "Monday" in str(error) and "Sunday" in str(error)
    assert error.extra_context() == {"date": "2026-10-05"}


def test_duplicate_positions_are_sorted_and_named() -> None:
    error = DuplicateSetlistPositionError({3, 2})
    assert isinstance(error, ValidationError)
    assert "[2, 3]" in str(error)
    assert error.extra_context() == {"positions": [2, 3]}


def test_setlist_not_found_names_the_date() -> None:
    error = SetlistNotFoundError(date(2026, 10, 4))
    assert isinstance(error, NotFoundError)
    assert "2026-10-04" in str(error)
    assert error.extra_context() == {"date": "2026-10-04"}
