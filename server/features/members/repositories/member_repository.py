from collections.abc import Collection
from uuid import UUID

from features.members.dtos import BirthdayDTO, MemberDTO, OwnMemberRecordDTO
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

    def list_names(self) -> list[MemberDTO]:
        """Every member, valid profile or not, by name then id: the gallery's tag picker, which
        the Mídia role reads, so nothing but id and name leaves here
        (specs/015-gallery-member-tags research R-03).

        >>> repo.list_names()
        [MemberDTO(id=40, name='João Lima'), MemberDTO(id=12, name='Maria Souza')]
        """
        qs = Member.objects.order_by("name", "id").values_list("id", "name")
        return [MemberDTO(id=pk, name=name) for pk, name in qs]

    def get_own_record(self, user_id: UUID) -> OwnMemberRecordDTO | None:
        """The roll record linked to the account ``user_id``, whatever its validity, or None.
        Reached through the profile's reverse lookup by string, so members never imports
        accounts.

        >>> repo.get_own_record(ana.pk).ministries
        ['Infantil', 'Louvor']
        """
        member = (
            Member.objects.select_related("role")
            .prefetch_related("ministries")
            .filter(profile__user_id=user_id)
            .first()
        )
        return _own_record(member) if member else None

    def existing_ids(self, member_ids: Collection[int]) -> set[int]:
        """The ids among ``member_ids`` that name a member, in one query.

        >>> repo.existing_ids([12, 999])
        {12}
        """
        return set(Member.objects.filter(pk__in=member_ids).values_list("id", flat=True))

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


def _own_record(member: Member) -> OwnMemberRecordDTO:
    return OwnMemberRecordDTO(
        id=member.pk,
        name=member.name,
        role=member.role.name if member.role else None,
        ministries=sorted(ministry.name for ministry in member.ministries.all()),
        birth_day=member.birth_day,
        birth_month=member.birth_month,
        birth_year=member.birth_year,
        baptism_date=member.baptism_date,
        gender=member.gender,
    )
