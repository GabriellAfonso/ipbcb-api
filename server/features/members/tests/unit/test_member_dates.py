from datetime import date

import pytest

from core.domain.exceptions import ValidationError
from features.members.domain.member_dates import validate_member_dates

TODAY = date(2026, 9, 25)


class TestValidateMemberDates:
    def test_future_birth_date_is_rejected_with_the_date(self) -> None:
        with pytest.raises(ValidationError, match="2026-09-26"):
            validate_member_dates(date(2026, 9, 26), None, TODAY)

    def test_future_baptism_date_is_rejected_with_the_date(self) -> None:
        with pytest.raises(ValidationError, match="2030-01-01"):
            validate_member_dates(None, date(2030, 1, 1), TODAY)

    def test_baptism_before_birth_is_rejected_with_both_dates(self) -> None:
        with pytest.raises(ValidationError, match="2000-01-01.*2001-01-01"):
            validate_member_dates(date(2001, 1, 1), date(2000, 1, 1), TODAY)

    @pytest.mark.parametrize(
        ("birth", "baptism"),
        [
            (date(2000, 1, 1), date(2000, 1, 1)),
            (None, date(2000, 1, 1)),
            (date(2000, 1, 1), None),
            (None, None),
            (TODAY, TODAY),
        ],
    )
    def test_accepts_valid_combinations(self, birth: date | None, baptism: date | None) -> None:
        validate_member_dates(birth, baptism, TODAY)
