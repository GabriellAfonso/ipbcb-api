"""US4 / US6 — the member-access rule end to end, and /me's access fields
(specs/022-access-requests FR-002 to FR-004)."""

import pytest
from rest_framework.test import APIClient

from conftest import make_auth_client, make_member_client, make_role_client, make_user
from core.domain.access import Role
from features.accounts.models.access_request import AccessRequest
from features.accounts.tests.integration.access_helpers import PROFILE_URL

pytestmark = pytest.mark.django_db

MEMBER_READS = [
    "/api/schedule/current/",
    "/api/members/",
    "/api/members/birthdays/?month=1",
    "/api/albums/",
]


def _role_client(role: Role) -> APIClient:
    return make_role_client(role, username=f"{role.value}_no_flag")[0]


class TestContentGate:
    @pytest.mark.parametrize("url", MEMBER_READS)
    @pytest.mark.parametrize("role", [Role.ADMIN, Role.LEADER])
    def test_leadership_without_flag_reads(self, url: str, role: Role) -> None:
        assert _role_client(role).get(url).status_code == 200

    @pytest.mark.parametrize("url", MEMBER_READS)
    def test_media_without_flag_is_refused(self, url: str) -> None:
        assert _role_client(Role.MEDIA).get(url).status_code == 403

    @pytest.mark.parametrize("url", MEMBER_READS)
    def test_flag_reads(self, url: str) -> None:
        assert make_member_client()[0].get(url).status_code == 200


class TestProfileFields:
    def test_flag_holder(self) -> None:
        data = make_member_client()[0].get(PROFILE_URL).data
        assert data["member_access"] is True
        assert data["is_member"] is True
        assert data["access_status"] == "granted"
        assert data["access_requests_blocked"] is False
        assert data["data_correction_pending"] is False

    def test_leader_without_flag(self) -> None:
        data = _role_client(Role.LEADER).get(PROFILE_URL).data
        assert data["member_access"] is True
        assert data["is_member"] is True
        assert data["access_status"] == "granted"

    def test_media_without_flag(self) -> None:
        data = _role_client(Role.MEDIA).get(PROFILE_URL).data
        assert data["member_access"] is False
        assert data["is_member"] is False
        assert data["access_status"] == "none"

    def test_pending_request(self) -> None:
        user = make_user(username="ana")
        AccessRequest.objects.create(user=user, type="access")
        data = make_auth_client(user).get(PROFILE_URL).data
        assert data["access_status"] == "pending"

    def test_patch_ignores_access_fields(self) -> None:
        user = make_user(username="ana")
        body = {
            "name": "Ana",
            "is_member": True,
            "member_access": True,
            "access_status": "granted",
            "access_requests_blocked": True,
        }
        response = make_auth_client(user).patch(PROFILE_URL, body, format="json")
        assert response.status_code == 200
        assert response.data["member_access"] is False
        user.profile.refresh_from_db()
        assert user.profile.member_access is False
        assert user.profile.access_requests_blocked is False

    def test_etag_changes_with_the_status(self) -> None:
        user = make_user(username="ana")
        client = make_auth_client(user)
        before = client.get(PROFILE_URL)["ETag"]
        AccessRequest.objects.create(user=user, type="access")
        assert client.get(PROFILE_URL, HTTP_IF_NONE_MATCH=before).status_code == 200
