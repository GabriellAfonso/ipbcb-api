"""Date sanity rules for member writes. Pure; "today" is passed in by the caller's clock.

Applied only to writes made through the leader endpoints: existing rows that break them
stay untouched until someone edits them (specs/010-members-management/spec.md).
Messages are in Portuguese: they reach the leader's screen through the error body.
"""

from datetime import date

from core.domain.exceptions import ValidationError


def validate_member_dates(birth_date: date | None, baptism_date: date | None, today: date) -> None:
    """Raise ``ValidationError`` for a future date or a baptism before birth.

    Called with the record as it would be after the write, so a patch that only moves the
    baptism date is still checked against the stored birth date.

    >>> validate_member_dates(date(1990, 4, 2), date(2005, 6, 12), date(2026, 9, 25))
    """
    _reject_future("nascimento", birth_date, today)
    _reject_future("batismo", baptism_date, today)
    if birth_date and baptism_date and baptism_date < birth_date:
        raise ValidationError(
            f"Data de batismo ({baptism_date.isoformat()}) anterior à data de nascimento "
            f"({birth_date.isoformat()})."
        )


def _reject_future(label: str, value: date | None, today: date) -> None:
    if value and value > today:
        raise ValidationError(
            f"Data de {label} no futuro: {value.isoformat()}. Use uma data até {today.isoformat()}."
        )
