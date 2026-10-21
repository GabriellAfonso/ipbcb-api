"""US2 — members also see members-only events; nobody else learns they exist
(specs/020-church-events FR-008 to FR-012)."""

from datetime import timedelta

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from conftest import make_auth_client, make_member_client, make_role_client, make_user
from core.domain.access import Role
from features.accounts.models.profile import Profile
from features.events.domain.event_enums import EventVisibility
from features.events.tests.integration.conftest import PUBLIC_URL, MakeEvent, public_detail_url

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("clock")]


def _ids(client: APIClient) -> list[int]:
    return [event["id"] for event in client.get(PUBLIC_URL).data]


def _non_member_callers() -> list[APIClient]:
    owner_client, _ = make_role_client(Role.ADMIN, username="admin_not_member")
    return [APIClient(), make_auth_client(make_user(username="visitor")), owner_client]


def test_member_sees_members_events_in_public_order(make_event: MakeEvent) -> None:
    later = make_event(start_date=make_event().start_date + timedelta(days=2))
    members = make_event(
        start_date=later.start_date - timedelta(days=1), visibility=EventVisibility.MEMBERS
    )
    client, _ = make_member_client()

    ids = _ids(client)

    assert ids.index(members.pk) < ids.index(later.pk)


def test_non_members_never_see_members_events(make_event: MakeEvent) -> None:
    public = make_event()
    make_event(visibility=EventVisibility.MEMBERS)

    for client in _non_member_callers():
        assert _ids(client) == [public.pk]


def test_members_event_detail_is_404_like_a_missing_id(make_event: MakeEvent) -> None:
    hidden = make_event(visibility=EventVisibility.MEMBERS)

    for client in _non_member_callers():
        hidden_response = client.get(public_detail_url(hidden.pk))
        missing_response = client.get(public_detail_url(hidden.pk + 1000))
        assert hidden_response.status_code == missing_response.status_code == 404
        assert set(hidden_response.data) == set(missing_response.data)
        assert hidden_response.data["error_code"] == missing_response.data["error_code"]


def test_member_reads_members_event_detail(make_event: MakeEvent) -> None:
    event = make_event(visibility=EventVisibility.MEMBERS)
    client, _ = make_member_client()

    assert client.get(public_detail_url(event.pk)).data["visibility"] == "members"


@pytest.mark.parametrize("url", [PUBLIC_URL, public_detail_url(1)])
def test_invalid_or_expired_token_is_401(url: str) -> None:
    malformed = APIClient()
    malformed.credentials(HTTP_AUTHORIZATION="Bearer not-a-jwt")
    token = AccessToken.for_user(make_user(username="expired"))
    token.set_exp(lifetime=-timedelta(minutes=1))
    expired = APIClient()
    expired.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    for client in (malformed, expired):
        assert client.get(url).status_code == 401


def test_user_without_profile_row_is_a_non_member(make_event: MakeEvent) -> None:
    public = make_event()
    make_event(visibility=EventVisibility.MEMBERS)
    user = make_user(username="no_profile")
    Profile.objects.filter(user=user).delete()

    assert _ids(make_auth_client(user)) == [public.pk]
