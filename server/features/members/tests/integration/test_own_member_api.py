"""US5 — GET api/me/member/: the caller's own roll record, never stored
(specs/022-access-requests FR-023, R-06)."""

from datetime import date

import pytest
from rest_framework.test import APIClient

from conftest import make_auth_client, make_user
from features.members.models.member import Member, Ministry, Role
from features.members.repositories.member_repository import MemberRepositoryImpl

pytestmark = pytest.mark.django_db

URL = "/api/me/member/"


def _linked_member() -> tuple[APIClient, Member]:
    user = make_user(username="ana")
    member = Member.objects.create(
        name="Ana Souza",
        birth_day=14,
        birth_month=3,
        gender="F",
        baptism_date=date(2001, 5, 20),
        role=Role.objects.create(name="Diaconisa"),
        is_active=False,
    )
    member.ministries.add(
        Ministry.objects.create(name="Louvor"), Ministry.objects.create(name="Infantil")
    )
    user.profile.member = member
    user.profile.save()
    return make_auth_client(user), member


def test_linked_account_reads_its_record() -> None:
    client, member = _linked_member()

    response = client.get(URL)

    assert response.status_code == 200
    assert response.data == {
        "id": member.pk,
        "name": "Ana Souza",
        "role": "Diaconisa",
        "ministries": ["Infantil", "Louvor"],
        "birth_day": 14,
        "birth_month": 3,
        "birth_year": None,
        "baptism_date": "2001-05-20",
        "gender": "F",
    }


def test_response_is_never_stored() -> None:
    client, _ = _linked_member()
    response = client.get(URL)
    assert response["Cache-Control"] == "private, no-store"
    assert "Authorization" in response["Vary"]
    assert "ETag" not in response


def test_unlinked_account() -> None:
    Member.objects.create(name="Someone else")
    response = make_auth_client(make_user(username="bia")).get(URL)
    assert response.status_code == 404
    assert response.data["error_code"] == "MEMBER_NOT_LINKED"


def test_anonymous() -> None:
    assert APIClient().get(URL).status_code == 401


def test_repository_reads_only_the_callers_record() -> None:
    _, member = _linked_member()
    other = make_user(username="carla")
    assert MemberRepositoryImpl().get_own_record(other.pk) is None
    record = MemberRepositoryImpl().get_own_record(member.profile.user.pk)
    assert record is not None and record.id == member.pk
