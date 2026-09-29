"""The member repository as the gallery's ``MemberDirectory`` (specs/015-gallery-member-tags
R-03): every member, valid profile or not, and nothing but id and name."""

import pytest

from features.members.dtos import MemberDTO
from features.members.models.member import Member
from features.members.repositories.member_repository import MemberRepositoryImpl


@pytest.mark.django_db
class TestDirectory:
    def test_list_names_is_every_member_by_name_then_id(self) -> None:
        carla = Member.objects.create(name="Carla")
        first_ana = Member.objects.create(name="Ana")
        inactive = Member.objects.create(name="Bruno", is_active=False)
        second_ana = Member.objects.create(name="Ana")  # same name: the id breaks the tie

        names = MemberRepositoryImpl().list_names()

        assert names == [
            MemberDTO(id=first_ana.pk, name="Ana"),
            MemberDTO(id=second_ana.pk, name="Ana"),
            MemberDTO(id=inactive.pk, name="Bruno"),
            MemberDTO(id=carla.pk, name="Carla"),
        ]

    def test_existing_ids_drops_unknown_ones(self) -> None:
        ana = Member.objects.create(name="Ana")

        assert MemberRepositoryImpl().existing_ids([ana.pk, 999_999]) == {ana.pk}

    def test_existing_ids_of_nothing_is_empty(self) -> None:
        assert MemberRepositoryImpl().existing_ids([]) == set()
