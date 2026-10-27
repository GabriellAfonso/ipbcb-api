"""Roll member -> account with member access (specs/024-schedule-reminders R-03)."""

import pytest
from django.contrib.auth.models import Group

from conftest import make_user
from core.domain.access import Role
from core.repositories.member_account_repository import MemberAccountRepositoryImpl
from features.accounts.models.user import User
from features.members.models.member import Member


def _linked(username: str, member_access: bool = False) -> tuple[User, Member]:
    user = make_user(username=username)
    member = Member.objects.create(name=username)
    user.profile.member = member
    user.profile.member_access = member_access
    user.profile.save()
    return user, member


@pytest.mark.django_db
class TestMemberAccountRepository:
    repository = MemberAccountRepositoryImpl()

    def test_flag_gives_access(self) -> None:
        user, member = _linked("ana", member_access=True)
        assert self.repository.user_ids_by_member({member.pk}) == {member.pk: user.pk}

    @pytest.mark.parametrize("role", [Role.ADMIN, Role.LEADER])
    def test_leadership_role_gives_access(self, role: Role) -> None:
        user, member = _linked("ana")
        user.groups.add(Group.objects.get(name=role.value))
        assert self.repository.user_ids_by_member({member.pk}) == {member.pk: user.pk}

    def test_media_role_alone_does_not(self) -> None:
        user, member = _linked("ana")
        user.groups.add(Group.objects.get(name=Role.MEDIA.value))
        assert self.repository.user_ids_by_member({member.pk}) == {}

    def test_linked_without_access_is_left_out(self) -> None:
        _, member = _linked("ana")
        assert self.repository.user_ids_by_member({member.pk}) == {}

    def test_inactive_account_is_left_out(self) -> None:
        user, member = _linked("ana", member_access=True)
        user.is_active = False
        user.save()
        assert self.repository.user_ids_by_member({member.pk}) == {}

    def test_only_requested_members(self) -> None:
        _linked("ana", member_access=True)
        bia_user, bia = _linked("bia", member_access=True)
        Member.objects.create(name="no account")
        assert self.repository.user_ids_by_member({bia.pk}) == {bia.pk: bia_user.pk}

    def test_flag_and_role_appear_once(self) -> None:
        user, member = _linked("ana", member_access=True)
        user.groups.add(*Group.objects.filter(name__in=[Role.ADMIN.value, Role.LEADER.value]))
        assert self.repository.user_ids_by_member({member.pk}) == {member.pk: user.pk}

    def test_empty_input_is_empty(self) -> None:
        assert self.repository.user_ids_by_member(set()) == {}
