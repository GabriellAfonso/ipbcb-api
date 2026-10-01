"""Worship flags on the profile (specs/017-sunday-setlist-push US4, contracts/me-api.md)."""

import pytest

from conftest import link_to_ministry, make_auth_client, make_role_client, make_user
from core.domain.access import Role

PROFILE_URL = "/api/me/profile/"


def _flags(data: dict[str, object]) -> tuple[object, object]:
    return data["is_worship_member"], data["can_save_setlist"]


@pytest.mark.django_db
class TestWorshipFlags:
    def test_leader_in_worship_can_save(self) -> None:
        client, user = make_role_client(Role.LEADER, username="leader")
        link_to_ministry(user)
        assert _flags(client.get(PROFILE_URL).data) == (True, True)

    def test_band_member_without_role_cannot_save(self) -> None:
        user = make_user(username="band")
        link_to_ministry(user)
        assert _flags(make_auth_client(user).get(PROFILE_URL).data) == (True, False)

    def test_leader_in_another_ministry_has_neither(self) -> None:
        client, user = make_role_client(Role.LEADER, username="leader")
        link_to_ministry(user, "Diaconia")
        assert _flags(client.get(PROFILE_URL).data) == (False, False)

    def test_admin_without_linked_member_has_neither(self) -> None:
        client, _ = make_role_client(Role.ADMIN, username="admin")
        assert _flags(client.get(PROFILE_URL).data) == (False, False)

    def test_media_in_worship_cannot_save(self) -> None:
        client, user = make_role_client(Role.MEDIA, username="media")
        link_to_ministry(user)
        assert _flags(client.get(PROFILE_URL).data) == (True, False)

    def test_etag_changes_when_joining_the_ministry(self) -> None:
        client, user = make_role_client(Role.LEADER, username="leader")
        before = client.get(PROFILE_URL)["ETag"]
        link_to_ministry(user)
        after = client.get(PROFILE_URL, HTTP_IF_NONE_MATCH=before)
        assert after.status_code == 200 and after["ETag"] != before

    def test_patch_ignores_the_flags(self) -> None:
        client, _ = make_role_client(Role.LEADER, username="leader")
        body = {"is_worship_member": True, "can_save_setlist": True}
        response = client.patch(PROFILE_URL, body, format="json")
        assert response.status_code == 200
        assert _flags(response.data) == (False, False)
