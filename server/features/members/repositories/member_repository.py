from features.members.dtos import BirthdayDTO, MemberDTO
from features.members.models.member import Member


class MemberRepositoryImpl:
    """Member repository using Django ORM."""

    def list_active_members(self) -> list[MemberDTO]:
        """Return all active members ordered by name.

        >>> repo.list_active_members()
        [MemberDTO(id=1, name='Alice'), ...]
        """
        qs = Member.objects.filter(is_active=True).order_by("name").values_list("id", "name")
        return [MemberDTO(id=pk, name=name) for pk, name in qs]

    def list_birthdays_by_month_range(self, start_month: int, end_month: int) -> list[BirthdayDTO]:
        """Return active members born in the given month range, ordered by month then day.

        >>> repo.list_birthdays_by_month_range(1, 6)
        [BirthdayDTO(name='Alice', gender='F', birth_month=1, birth_day=5), ...]
        """
        # birth_day set implies birth_month set (member_birth_day_month_together constraint),
        # so year-only and empty members drop out with one null check.
        qs = (
            Member.objects.filter(
                is_active=True,
                birth_day__isnull=False,
                birth_month__gte=start_month,
                birth_month__lte=end_month,
            )
            .order_by("birth_month", "birth_day")
            .values_list("name", "gender", "birth_month", "birth_day")
        )
        # The query already excludes empty parts; the check only narrows the types for mypy.
        return [
            BirthdayDTO(name=name, gender=gender, birth_month=month, birth_day=day)
            for name, gender, month, day in qs
            if month is not None and day is not None
        ]
