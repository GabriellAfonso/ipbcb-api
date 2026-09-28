from datetime import date

import pytest

from core.domain.exceptions import ValidationError
from features.members.domain.member_dates import (
    BirthDateParts,
    validate_member_date_parts,
)

TODAY = date(2026, 9, 28)


class TestValidateMemberDateParts:
    @pytest.mark.parametrize(
        ("birth", "baptism", "offending"),
        [
            (BirthDateParts(0, 3, None), None, "birth_day=0"),
            (BirthDateParts(12, 13, None), None, "birth_month=13"),
            (BirthDateParts(None, None, 0), None, "birth_year=0"),
            (BirthDateParts(12, None, None), None, "birth_day=12, birth_month=None"),
            (BirthDateParts(None, 3, 1990), None, "birth_day=None, birth_month=3"),
            (BirthDateParts(31, 4, None), None, "31/04"),
            (BirthDateParts(30, 2, None), None, "30/02"),
            (BirthDateParts(29, 2, 1990), None, "29/02/1990"),
            (BirthDateParts(None, None, 2027), None, "birth_year=2027"),
            (BirthDateParts(1, 10, 2026), None, "2026-10-01"),
            (BirthDateParts(12, 3, 1990), date(1990, 3, 11), r"1990-03-11.*1990-03-12"),
            (BirthDateParts(None, None, 1990), date(1989, 12, 31), r"1989-12-31.*1990"),
            (BirthDateParts(None, None, None), date(2026, 9, 29), "2026-09-29"),
        ],
    )
    def test_rejects_with_the_offending_value(
        self, birth: BirthDateParts, baptism: date | None, offending: str
    ) -> None:
        with pytest.raises(ValidationError, match=offending):
            validate_member_date_parts(birth, baptism, TODAY)

    @pytest.mark.parametrize(
        ("birth", "baptism"),
        [
            (BirthDateParts(12, 3, 1990), None),
            (BirthDateParts(12, 3, None), None),
            (BirthDateParts(None, None, 1950), None),
            (BirthDateParts(None, None, None), None),
            (BirthDateParts(31, 12, 1), None),
            (BirthDateParts(29, 2, None), None),
            (BirthDateParts(29, 2, 2000), None),
            (BirthDateParts(1, 10, None), None),
            (BirthDateParts(None, None, 2026), None),
            (BirthDateParts(28, 9, 2026), None),
            (BirthDateParts(12, 3, 1990), date(1990, 3, 12)),
            (BirthDateParts(None, None, 1990), date(1990, 1, 1)),
            (BirthDateParts(12, 3, None), date(1900, 1, 1)),
        ],
    )
    def test_accepts_valid_combinations(self, birth: BirthDateParts, baptism: date | None) -> None:
        validate_member_date_parts(birth, baptism, TODAY)

    def test_label_omits_unknown_year(self) -> None:
        assert BirthDateParts(5, 8, None).label() == "05/08"
        assert BirthDateParts(5, 8, 1950).label() == "05/08/1950"

    def test_full_date_needs_every_part(self) -> None:
        assert BirthDateParts(5, 8, 1950).full_date() == date(1950, 8, 5)
        assert BirthDateParts(5, 8, None).full_date() is None
