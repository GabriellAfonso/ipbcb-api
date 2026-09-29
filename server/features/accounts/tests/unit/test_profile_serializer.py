import pytest
from unittest.mock import Mock
from core.application.dtos.access_dtos import AccessGrantsDTO
from core.domain.access import Role, resolve_grants
from features.accounts.serializers.serializers import ProfileSerializer
from conftest import make_user


def test_photo_url_returns_absolute_uri() -> None:
    profile = Mock()
    profile.photo = Mock()
    profile.photo.url = "/ipbcb/media/profiles/user/photo.jpg"

    request = Mock()
    request.build_absolute_uri.return_value = (
        "http://testserver/ipbcb/media/profiles/user/photo.jpg"
    )

    s = ProfileSerializer(context={"request": request})
    result = s.get_photo_url(profile)

    assert result == "http://testserver/ipbcb/media/profiles/user/photo.jpg"
    request.build_absolute_uri.assert_called_once_with(profile.photo.url)


def test_photo_url_returns_none_when_no_photo() -> None:
    profile = Mock()
    profile.photo = None

    request = Mock()

    s = ProfileSerializer(context={"request": request})
    assert s.get_photo_url(profile) is None


@pytest.mark.django_db
def test_read_only_fields_not_writable() -> None:
    user = make_user(username="rotest", password="testpass123")
    profile = user.profile

    s = ProfileSerializer(
        profile,
        data={"is_admin": True, "is_member": True, "roles": [], "name": "Allowed"},
        partial=True,
    )
    assert s.is_valid(), s.errors
    assert "is_admin" not in s.validated_data
    assert "is_member" not in s.validated_data
    assert "roles" not in s.validated_data
    assert "name" in s.validated_data


@pytest.mark.django_db
def test_name_is_writable() -> None:
    user = make_user(username="nametest", password="testpass123")
    profile = user.profile

    s = ProfileSerializer(profile, data={"name": "New Name"}, partial=True)
    assert s.is_valid(), s.errors
    s.save()

    profile.refresh_from_db()
    assert profile.name == "New Name"


def _grants(*roles: Role) -> AccessGrantsDTO:
    codenames = MEDIA_CODENAMES if Role.MEDIA in roles else []
    return AccessGrantsDTO(roles=list(roles), levels=resolve_grants(list(roles), codenames))


MEDIA_CODENAMES = [
    "gallery__manage",
    "events__manage",
    "notices__manage",
    "reports_hymnal_history__view",
]


def test_roles_and_permissions_for_media() -> None:
    s = ProfileSerializer(context={"access_grants": _grants(Role.MEDIA)})
    profile = Mock()
    assert s.get_roles(profile) == [{"id": "media", "name": "Mídia"}]
    assert s.get_permissions(profile) == {
        "members": None,
        "schedule": None,
        "songs": None,
        "gallery": "manage",
        "events": "manage",
        "notices": "manage",
        "reports.hymnal_history": "view",
    }


def test_no_role_lists_every_scope_as_null() -> None:
    s = ProfileSerializer(context={"access_grants": _grants()})
    assert s.get_roles(Mock()) == []
    assert set(s.get_permissions(Mock()).values()) == {None}
    assert len(s.get_permissions(Mock())) == 7


def test_admin_owns_every_scope() -> None:
    s = ProfileSerializer(context={"access_grants": _grants(Role.ADMIN)})
    assert set(s.get_permissions(Mock()).values()) == {"owner"}


def test_missing_grants_is_an_error_not_an_empty_role_list() -> None:
    s = ProfileSerializer(context={})
    with pytest.raises(KeyError, match="access_grants"):
        s.get_roles(Mock())
