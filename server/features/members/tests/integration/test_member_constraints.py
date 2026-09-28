"""Database checks on the birth date parts (specs/011-split-birth-date/research.md R-01).

They exist for writes that skip the service, the Django admin above all, so they are tested
against the database and through ``full_clean`` (what the admin form runs).
"""

import pytest
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction

from features.members.models.member import Member


@pytest.mark.django_db
class TestMemberBirthConstraints:
    @pytest.mark.parametrize(
        "parts",
        [
            {"birth_day": 12, "birth_month": None},
            {"birth_day": None, "birth_month": 3},
            {"birth_day": 32, "birth_month": 1},
            {"birth_day": 1, "birth_month": 13},
            {"birth_day": 0, "birth_month": 1},
        ],
    )
    def test_database_refuses_invalid_parts(self, parts: dict[str, int | None]) -> None:
        with pytest.raises(IntegrityError), transaction.atomic():
            Member.objects.create(name="Ana", **parts)

    @pytest.mark.parametrize(
        "parts",
        [
            {"birth_day": 12, "birth_month": 3, "birth_year": 1990},
            {"birth_day": 12, "birth_month": 3, "birth_year": None},
            {"birth_day": None, "birth_month": None, "birth_year": 1950},
            {"birth_day": None, "birth_month": None, "birth_year": None},
        ],
    )
    def test_database_stores_each_valid_state(self, parts: dict[str, int | None]) -> None:
        member = Member.objects.create(name="Ana", **parts)
        member.refresh_from_db()
        assert (member.birth_day, member.birth_month, member.birth_year) == tuple(parts.values())

    def test_full_clean_reports_the_pair_constraint(self) -> None:
        with pytest.raises(DjangoValidationError, match="member_birth_day_month_together"):
            Member(name="Ana", birth_day=12).full_clean()
