"""The profile's link to its member record (specs/015-gallery-member-tags US3, FR-001–FR-006).

Member rows are built through the app registry: accounts never imports the members feature.
"""

from typing import Any

import pytest
from django.apps import apps
from django.test import Client

from conftest import make_auth_client, make_user
from features.accounts.models.user import User

PROFILE_URL = "/api/me/profile/"


def _member(name: str = "Ana") -> Any:
    return apps.get_model("members", "Member").objects.create(name=name)


def _admin_client() -> Client:
    staff = make_user(username="staff")
    staff.is_staff = staff.is_superuser = True
    staff.save()
    client = Client()
    client.force_login(staff)
    return client


def _link(user: User, member: Any) -> None:
    user.profile.member = member
    user.profile.save()


@pytest.mark.django_db
class TestProfileResource:
    def test_unlinked_profile_has_null_member_id(self) -> None:
        user = make_user(username="unlinked")

        data = make_auth_client(user).get(PROFILE_URL).data

        assert data["member_id"] is None
        # Worship flags added by specs/017-sunday-setlist-push US4.
        assert set(data) == {
            "name",
            "is_member",
            "photo_url",
            "roles",
            "permissions",
            "member_id",
            "is_worship_member",
            "can_save_setlist",
        }

    def test_linked_profile_carries_the_member_id(self) -> None:
        user = make_user(username="linked")
        member = _member()
        _link(user, member)

        assert make_auth_client(user).get(PROFILE_URL).data["member_id"] == member.pk

    def test_etag_changes_when_the_link_changes(self) -> None:
        user = make_user(username="etag_link")
        client = make_auth_client(user)
        first = client.get(PROFILE_URL)["ETag"]
        _link(user, _member())

        assert client.get(PROFILE_URL, HTTP_IF_NONE_MATCH=first).status_code == 200

    def test_patch_ignores_member_id(self) -> None:
        user = make_user(username="patcher")
        member, other = _member(), _member("Bruno")
        _link(user, member)

        response = make_auth_client(user).patch(
            PROFILE_URL, {"name": "Novo", "member_id": other.pk}, format="json"
        )

        user.profile.refresh_from_db()
        assert response.status_code == 200
        assert (response.data["member_id"], user.profile.member_id) == (member.pk, member.pk)

    def test_deleting_the_member_unlinks_and_keeps_the_profile(self) -> None:
        user = make_user(username="orphan")
        member = _member()
        _link(user, member)

        member.delete()

        user.profile.refresh_from_db()
        assert user.profile.member_id is None
        assert User.objects.filter(pk=user.pk).exists()

    @pytest.mark.parametrize("is_member", [True, False])
    def test_is_member_is_independent_of_the_link(self, is_member: bool) -> None:
        user = make_user(username=f"flag_{is_member}")
        user.profile.is_member = is_member
        user.profile.save()
        _link(user, _member())

        user.profile.refresh_from_db()
        assert user.profile.is_member is is_member


@pytest.mark.django_db
class TestDjangoAdmin:
    def test_second_link_to_the_same_member_is_a_form_error(self) -> None:
        member = _member()
        _link(make_user(username="first"), member)
        second = make_user(username="second")

        response = _admin_client().post(
            f"/admin/accounts/profile/{second.profile.pk}/change/",
            {"user": second.pk, "name": "Second", "member": member.pk},
        )

        second.profile.refresh_from_db()
        assert response.status_code == 200  # the form again, with the error
        assert response.context["adminform"].form.errors["member"]
        assert second.profile.member_id is None

    def test_member_autocomplete_searches_by_name(self) -> None:
        _member("Ana Souza")
        _member("Bruno Lima")

        response = _admin_client().get(
            "/admin/autocomplete/",
            {
                "term": "Ana",
                "app_label": "accounts",
                "model_name": "profile",
                "field_name": "member",
            },
        )

        assert response.status_code == 200
        assert [r["text"] for r in response.json()["results"]] == ["Ana Souza"]
