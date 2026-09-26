from collections.abc import Callable
from contextlib import AbstractContextManager

import pytest

from conftest import make_user
from features.members.dtos import MemberFieldChange
from features.members.models.member import Member
from features.members.models.member_change_log import MemberChangeLog
from features.members.repositories.member_change_log_repository import (
    MemberChangeLogRepositoryImpl,
)

AssertNumQueries = Callable[[int], AbstractContextManager[object]]


def _change(field: str) -> MemberFieldChange:
    return MemberFieldChange(field=field, old_value="a", new_value="b")


@pytest.mark.django_db
class TestAddEntries:
    def test_writes_all_rows_in_one_query(
        self, django_assert_num_queries: AssertNumQueries
    ) -> None:
        member = Member.objects.create(name="Ana")
        editor = make_user(username="leader")

        with django_assert_num_queries(1):
            MemberChangeLogRepositoryImpl().add_entries(
                member.pk, editor.pk, [_change("name"), _change("gender")]
            )

        assert MemberChangeLog.objects.filter(member=member, editor=editor).count() == 2

    def test_empty_list_writes_nothing(self) -> None:
        member = Member.objects.create(name="Ana")

        MemberChangeLogRepositoryImpl().add_entries(member.pk, None, [])

        assert not MemberChangeLog.objects.exists()


@pytest.mark.django_db
class TestListForMember:
    def test_newest_first_with_profile_name(self) -> None:
        editor = make_user(username="leader")
        editor.profile.name = "Pr. João"
        editor.profile.save()
        member = Member.objects.create(name="Ana")
        repo = MemberChangeLogRepositoryImpl()
        repo.add_entries(member.pk, editor.pk, [_change("name")])
        repo.add_entries(member.pk, editor.pk, [_change("gender")])

        entries = repo.list_for_member(member.pk)

        assert [e.field for e in entries] == ["gender", "name"]
        assert entries[0].editor is not None
        assert entries[0].editor.name == "Pr. João"
        assert entries[0].editor.id == str(editor.pk)

    def test_username_when_profile_name_is_blank(self) -> None:
        editor = make_user(username="leader")
        editor.profile.name = ""
        editor.profile.save()
        member = Member.objects.create(name="Ana")
        MemberChangeLogRepositoryImpl().add_entries(member.pk, editor.pk, [_change("name")])

        (entry,) = MemberChangeLogRepositoryImpl().list_for_member(member.pk)

        assert entry.editor is not None and entry.editor.name == "leader"

    def test_deleted_editor_reads_as_none(self) -> None:
        editor = make_user(username="leader")
        member = Member.objects.create(name="Ana")
        MemberChangeLogRepositoryImpl().add_entries(member.pk, editor.pk, [_change("name")])
        editor.delete()

        (entry,) = MemberChangeLogRepositoryImpl().list_for_member(member.pk)

        assert entry.editor is None

    def test_one_query_for_many_entries(self, django_assert_num_queries: AssertNumQueries) -> None:
        editor = make_user(username="leader")
        member = Member.objects.create(name="Ana")
        MemberChangeLogRepositoryImpl().add_entries(
            member.pk, editor.pk, [_change(f"f{i}") for i in range(10)]
        )

        with django_assert_num_queries(1):
            entries = MemberChangeLogRepositoryImpl().list_for_member(member.pk)

        assert len(entries) == 10

    def test_only_this_members_entries(self) -> None:
        ana = Member.objects.create(name="Ana")
        bruno = Member.objects.create(name="Bruno")
        MemberChangeLogRepositoryImpl().add_entries(bruno.pk, None, [_change("name")])

        assert MemberChangeLogRepositoryImpl().list_for_member(ana.pk) == []
