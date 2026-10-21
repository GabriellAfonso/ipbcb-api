from uuid import UUID

from features.members.dtos import BirthdayDTO, MemberDTO, OwnMemberRecordDTO
from features.members.services.member_service import MemberService


class FakeMemberRepository:
    def __init__(self, birthdays: list[BirthdayDTO]) -> None:
        self._birthdays = birthdays
        self.last_start_month: int | None = None
        self.last_end_month: int | None = None

    def list_active_members(self) -> list[MemberDTO]:
        return []

    def list_birthdays_by_month_range(self, start_month: int, end_month: int) -> list[BirthdayDTO]:
        self.last_start_month = start_month
        self.last_end_month = end_month
        return self._birthdays

    def get_own_record(self, user_id: UUID) -> OwnMemberRecordDTO | None:
        return None


class TestMemberService:
    def test_list_birthdays_by_month_range_delegates_to_repository(self) -> None:
        expected = [
            BirthdayDTO(name="Alice", gender="F", birth_month=7, birth_day=5),
            BirthdayDTO(name="Bob", gender="M", birth_month=7, birth_day=23),
        ]
        repo = FakeMemberRepository(expected)
        service = MemberService(repository=repo)

        result = service.list_birthdays_by_month_range(7, 7)

        assert result == expected
        assert repo.last_start_month == 7
        assert repo.last_end_month == 7

    def test_list_birthdays_by_month_range_returns_empty_list(self) -> None:
        repo = FakeMemberRepository([])
        service = MemberService(repository=repo)

        result = service.list_birthdays_by_month_range(1, 6)

        assert result == []
        assert repo.last_start_month == 1
        assert repo.last_end_month == 6

    def test_list_birthdays_by_month_range_with_range(self) -> None:
        expected = [
            BirthdayDTO(name="Alice", gender="F", birth_month=1, birth_day=5),
            BirthdayDTO(name="Bob", gender="M", birth_month=3, birth_day=10),
        ]
        repo = FakeMemberRepository(expected)
        service = MemberService(repository=repo)

        result = service.list_birthdays_by_month_range(1, 6)

        assert result == expected
        assert repo.last_start_month == 1
        assert repo.last_end_month == 6
