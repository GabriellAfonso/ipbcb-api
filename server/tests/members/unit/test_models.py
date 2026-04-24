import pytest

from features.members.models.member import Member, MemberStatus, Ministry, Role


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
