import pytest

from conftest import make_user
from features.members.models.member import Member, MemberStatus, Ministry, Role
from features.members.models.member_change_log import MemberChangeLog


@pytest.mark.django_db
class TestMemberStatusStr:
    def test_returns_name(self) -> None:
        status = MemberStatus.objects.create(name="Active")
        assert str(status) == "Active"


@pytest.mark.django_db
class TestRoleStr:
    def test_returns_name(self) -> None:
        role = Role.objects.create(name="Elder")
        assert str(role) == "Elder"


@pytest.mark.django_db
class TestMinistryStr:
    def test_returns_name(self) -> None:
        ministry = Ministry.objects.create(name="Music")
        assert str(ministry) == "Music"


@pytest.mark.django_db
class TestMemberStr:
    def test_returns_name(self) -> None:
        member = Member.objects.create(name="John Doe")
        assert str(member) == "John Doe"


@pytest.mark.django_db
class TestMemberChangeLog:
    def test_str_carries_no_member_name(self) -> None:
        member = Member.objects.create(name="Maria Sigilo")
        entry = MemberChangeLog.objects.create(member=member, field="name")

        assert "Maria" not in str(entry)
        assert str(member.pk) in str(entry)

    def test_default_ordering_is_newest_first(self) -> None:
        member = Member.objects.create(name="A")
        first = MemberChangeLog.objects.create(member=member, field="name")
        second = MemberChangeLog.objects.create(member=member, field="gender")

        assert list(MemberChangeLog.objects.all()) == [second, first]

    def test_member_delete_removes_its_entries(self) -> None:
        member = Member.objects.create(name="A")
        MemberChangeLog.objects.create(member=member, field="name")

        member.delete()

        assert not MemberChangeLog.objects.exists()

    def test_editor_delete_keeps_entries(self) -> None:
        editor = make_user(username="leader")
        member = Member.objects.create(name="A")
        entry = MemberChangeLog.objects.create(member=member, editor=editor, field="name")

        editor.delete()
        entry.refresh_from_db()

        assert entry.editor is None
