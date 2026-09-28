"""Date sanity rules for member writes. Pure; "today" is passed in by the caller's clock.

Applied only to writes made through the leader endpoints: existing rows that break them
stay untouched until someone edits them (specs/010-members-management/spec.md).
Messages are in Portuguese: they reach the leader's screen through the error body.
"""

import calendar
from dataclasses import dataclass
from datetime import date

from core.domain.exceptions import ValidationError

# Any leap year works: it only decides whether 29/02 exists when the birth year is unknown.
_LEAP_YEAR_FALLBACK = 2000


@dataclass(frozen=True)
class BirthDateParts:
    """A birth date as far as it is known: day and month go together, year is independent.

    >>> BirthDateParts(day=12, month=3, year=None).full_date()
    """

    day: int | None
    month: int | None
    year: int | None

    def full_date(self) -> date | None:
        """The calendar date when all three parts are known and valid, else None."""
        if self.day is None or self.month is None or self.year is None:
            return None
        return date(self.year, self.month, self.day)

    def label(self) -> str:
        """``DD/MM`` or ``DD/MM/YYYY`` for messages; only called when day and month are set."""
        text = f"{self.day:02d}/{self.month:02d}"
        return f"{text}/{self.year}" if self.year is not None else text


def validate_member_date_parts(
    birth: BirthDateParts, baptism_date: date | None, today: date
) -> None:
    """Raise ``ValidationError`` for an impossible, future or inconsistent birth date.

    Called with the record as it would be after the write, so a patch sending only the day
    is checked against the stored month (specs/011-split-birth-date/spec.md FR-006).

    >>> validate_member_date_parts(BirthDateParts(2, 4, None), date(2005, 6, 12), today)
    """
    _check_part_ranges(birth)
    _check_day_month_pair(birth)
    _check_calendar_date(birth)
    _check_birth_not_future(birth, today)
    _reject_future("batismo", baptism_date, today)
    _check_baptism_after_birth(birth, baptism_date)


def _check_part_ranges(birth: BirthDateParts) -> None:
    # 9999 only keeps date() from overflowing; the real ceiling is the current year.
    parts = (("birth_day", birth.day, 31), ("birth_month", birth.month, 12))
    for name, value, highest in (*parts, ("birth_year", birth.year, 9999)):
        if value is not None and not 1 <= value <= highest:
            raise ValidationError(
                f"Valor fora do intervalo: {name}={value}. Esperado um inteiro de 1 a {highest}."
            )


def _check_day_month_pair(birth: BirthDateParts) -> None:
    if (birth.day is None) != (birth.month is None):
        raise ValidationError(
            f"Dia e mês de nascimento vão juntos: birth_day={birth.day}, "
            f"birth_month={birth.month}. Envie os dois ou nenhum."
        )


def _check_calendar_date(birth: BirthDateParts) -> None:
    if birth.day is None or birth.month is None:
        return
    year = birth.year if birth.year is not None else _LEAP_YEAR_FALLBACK
    last_day = calendar.monthrange(year, birth.month)[1]
    if birth.day > last_day:
        scope = f"{birth.month:02d}/{birth.year}" if birth.year is not None else "o mês"
        raise ValidationError(
            f"Data de nascimento inexistente: {birth.label()}. "
            f"Em {scope} o último dia é {last_day}."
        )


def _check_birth_not_future(birth: BirthDateParts, today: date) -> None:
    if birth.year is not None and birth.year > today.year:
        raise ValidationError(
            f"Ano de nascimento no futuro: birth_year={birth.year}. Use um ano até {today.year}."
        )
    _reject_future("nascimento", birth.full_date(), today)


def _check_baptism_after_birth(birth: BirthDateParts, baptism_date: date | None) -> None:
    # Only what is known is compared: with day and month alone there is nothing to compare.
    if baptism_date is None or birth.year is None:
        return
    full_date = birth.full_date()
    if full_date is not None and baptism_date < full_date:
        raise ValidationError(
            f"Data de batismo ({baptism_date.isoformat()}) anterior à data de nascimento "
            f"({full_date.isoformat()})."
        )
    if full_date is None and baptism_date.year < birth.year:
        raise ValidationError(
            f"Data de batismo ({baptism_date.isoformat()}) anterior ao ano de nascimento "
            f"({birth.year})."
        )


def _reject_future(label: str, value: date | None, today: date) -> None:
    if value and value > today:
        raise ValidationError(
            f"Data de {label} no futuro: {value.isoformat()}. Use uma data até {today.isoformat()}."
        )
