from collections.abc import Callable
from contextlib import AbstractContextManager

import pytest

from features.members.dtos import MemberCreateDTO, MemberPatchDTO, NamedRefDTO
from features.members.models.member import Member, MemberStatus, Ministry, Role
from features.members.repositories.member_roster_repository import MemberRosterRepositoryImpl

AssertNumQueries = Callable[[int], AbstractContextManager[object]]


@pytest.fixture
def repo() -> MemberRosterRepositoryImpl:
    return MemberRosterRepositoryImpl()


@pytest.mark.django_db
class TestListMembers:
    def test_includes_invalid_profiles_ordered_by_name(
        self, repo: MemberRosterRepositoryImpl
    ) -> None:
        status = MemberStatus.objects.create(name="Comungante")
        Member.objects.create(name="Bruno", is_active=False)
        Member.objects.create(name="Ana", status=status)

        members = repo.list_members()

        assert [m.name for m in members] == ["Ana", "Bruno"]
        assert members[0].status == NamedRefDTO(id=status.pk, name="Comungante")
        assert members[1].is_active is False
        assert members[1].photo_path is None

    def test_query_count_does_not_grow_with_members(
        self, repo: MemberRosterRepositoryImpl, django_assert_num_queries: AssertNumQueries
    ) -> None:
        status = MemberStatus.objects.create(name="Comungante")
        for i in range(20):
            Member.objects.create(name=f"M{i}", status=status)

        with django_assert_num_queries(1):
            repo.list_members()


@pytest.mark.django_db
class TestGetRecord:
    def test_full_record_with_sorted_ministries(
        self, repo: MemberRosterRepositoryImpl, django_assert_num_queries: AssertNumQueries
    ) -> None:
        role = Role.objects.create(name="Diácono")
        member = Member.objects.create(
            name="Ana", role=role, birth_day=2, birth_month=4, birth_year=1990
        )
        member.ministries.set(
            [Ministry.objects.create(name="Recepção"), Ministry.objects.create(name="Louvor")]
        )

        with django_assert_num_queries(2):
            record = repo.get_record(member.pk)

        assert record is not None
        assert [m.name for m in record.ministries] == ["Louvor", "Recepção"]
        assert record.role == NamedRefDTO(id=role.pk, name="Diácono")
        assert record.status is None
        assert (record.birth_day, record.birth_month, record.birth_year) == (2, 4, 1990)

    def test_unknown_id_returns_none(self, repo: MemberRosterRepositoryImpl) -> None:
        assert repo.get_record(999) is None


@pytest.mark.django_db
class TestLookups:
    def test_options_ordered_by_name(self, repo: MemberRosterRepositoryImpl) -> None:
        MemberStatus.objects.create(name="Não comungante")
        MemberStatus.objects.create(name="Comungante")

        options = repo.get_options()

        assert [s.name for s in options.statuses] == ["Comungante", "Não comungante"]
        assert options.roles == [] and options.ministries == []

    def test_find_status_and_role_unknown_is_none(self, repo: MemberRosterRepositoryImpl) -> None:
        assert repo.find_status(999) is None
        assert repo.find_role(999) is None

    def test_find_ministries_returns_existing_only_in_one_query(
        self, repo: MemberRosterRepositoryImpl, django_assert_num_queries: AssertNumQueries
    ) -> None:
        louvor = Ministry.objects.create(name="Louvor")

        with django_assert_num_queries(1):
            found = repo.find_ministries([louvor.pk, 999])

        assert found == [NamedRefDTO(id=louvor.pk, name="Louvor")]


@pytest.mark.django_db
class TestWrites:
    def test_create_persists_fields_and_ministries(self, repo: MemberRosterRepositoryImpl) -> None:
        status = MemberStatus.objects.create(name="Comungante")
        louvor = Ministry.objects.create(name="Louvor")

        member_id = repo.create(
            MemberCreateDTO(name="Ana", gender="F", status_id=status.pk, ministry_ids=[louvor.pk])
        )

        member = Member.objects.get(pk=member_id)
        assert (member.name, member.gender, member.status_id) == ("Ana", "F", status.pk)
        assert list(member.ministries.all()) == [louvor]

    def test_update_applies_only_sent_fields(self, repo: MemberRosterRepositoryImpl) -> None:
        status = MemberStatus.objects.create(name="Comungante")
        member = Member.objects.create(name="Ana", gender="F", status=status)

        repo.update(member.pk, MemberPatchDTO(name="Ana Souza", status_id=None))

        member.refresh_from_db()
        assert (member.name, member.gender, member.status_id) == ("Ana Souza", "F", None)

    def test_update_replaces_ministries(self, repo: MemberRosterRepositoryImpl) -> None:
        louvor = Ministry.objects.create(name="Louvor")
        recepcao = Ministry.objects.create(name="Recepção")
        member = Member.objects.create(name="Ana")
        member.ministries.set([louvor])

        repo.update(member.pk, MemberPatchDTO(ministry_ids=[recepcao.pk]))

        assert list(member.ministries.all()) == [recepcao]

    def test_photo_name_round_trip(self, repo: MemberRosterRepositoryImpl) -> None:
        member = Member.objects.create(name="Ana")
        assert repo.get_photo_name(member.pk) is None

        repo.set_photo_name(member.pk, "members/abc.jpg")
        assert repo.get_photo_name(member.pk) == "members/abc.jpg"

        repo.set_photo_name(member.pk, None)
        assert repo.get_photo_name(member.pk) is None

    def test_delete(self, repo: MemberRosterRepositoryImpl) -> None:
        member = Member.objects.create(name="Ana")

        repo.delete(member.pk)

        assert not repo.exists(member.pk)
