"""Worship membership by ministry name (specs/017-sunday-setlist-push R-03, plan OQ-1)."""

import pytest

from conftest import link_to_ministry, make_user
from core.repositories.worship_repository import WorshipMembershipRepositoryImpl
from features.members.models.member import Member, Ministry


@pytest.mark.django_db
class TestWorshipMembershipRepository:
    repository = WorshipMembershipRepositoryImpl()

    @pytest.mark.parametrize("name", ["Louvor", "louvor", "LOUVOR", "  Louvor  "])
    def test_name_variants_count(self, name: str) -> None:
        user = make_user(username="ana")
        link_to_ministry(user, name)
        assert self.repository.is_worship_member(user.pk)
        assert self.repository.worship_member_user_ids() == {user.pk}

    def test_both_matching_ministries_count(self) -> None:
        first, second = make_user(username="ana"), make_user(username="bia")
        link_to_ministry(first, "Louvor")
        link_to_ministry(second, " louvor ")
        assert self.repository.worship_member_user_ids() == {first.pk, second.pk}

    def test_profile_without_member_is_not(self) -> None:
        Ministry.objects.create(name="Louvor")
        user = make_user(username="ana")
        assert not self.repository.is_worship_member(user.pk)

    def test_member_of_another_ministry_is_not(self) -> None:
        user = make_user(username="ana")
        link_to_ministry(user, "Louvor e Artes")
        assert not self.repository.is_worship_member(user.pk)
        assert self.repository.worship_member_user_ids() == set()

    def test_inactive_user_is_not(self) -> None:
        user = make_user(username="ana")
        link_to_ministry(user)
        user.is_active = False
        user.save()
        assert not self.repository.is_worship_member(user.pk)
        assert self.repository.worship_member_user_ids() == set()

    def test_invalid_member_record_still_counts(self) -> None:
        # Member.is_active means "valid profile" and is not considered (plan OQ-1: A).
        user = make_user(username="ana")
        link_to_ministry(user, is_active=False)
        assert self.repository.is_worship_member(user.pk)

    def test_member_in_several_ministries_appears_once(self) -> None:
        user = make_user(username="ana")
        member = link_to_ministry(user)
        member.ministries.add(Ministry.objects.create(name="Diaconia"))
        assert self.repository.worship_member_user_ids() == {user.pk}

    def test_ministry_exists(self) -> None:
        assert not self.repository.worship_ministry_exists()
        Ministry.objects.create(name=" LOUVOR ")
        assert self.repository.worship_ministry_exists()

    def test_renamed_ministry_does_not_exist(self) -> None:
        Ministry.objects.create(name="Música")
        Member.objects.create(name="x")
        assert not self.repository.worship_ministry_exists()
