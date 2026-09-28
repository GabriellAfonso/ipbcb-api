"""seed_birthdays writes the birth parts, partly known dates included (spec 011 FR-018)."""

import pytest
from django.core.management import call_command

from features.members.management.commands.seed_birthdays import FAKE_MEMBERS
from features.members.models.member import Member


@pytest.mark.django_db
class TestSeedBirthdays:
    def test_seeds_every_entry_with_its_parts(self) -> None:
        call_command("seed_birthdays")

        stored = {
            m.name: (m.gender, m.birth_day, m.birth_month, m.birth_year)
            for m in Member.objects.all()
        }
        assert stored == {name: tuple(rest) for name, *rest in FAKE_MEMBERS}

    def test_clear_removes_seeded_members(self) -> None:
        call_command("seed_birthdays")

        call_command("seed_birthdays", "--clear")

        assert not Member.objects.exists()
