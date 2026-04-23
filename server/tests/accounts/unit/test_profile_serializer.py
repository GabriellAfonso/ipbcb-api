import pytest
from unittest.mock import Mock
from features.accounts.serializers.serializers import ProfileSerializer
from tests.conftest import make_user


def test_photo_url_returns_absolute_uri():
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


def test_photo_url_returns_none_when_no_photo():
    profile = Mock()
    profile.photo = None

    request = Mock()

    s = ProfileSerializer(context={"request": request})
    assert s.get_photo_url(profile) is None


@pytest.mark.django_db
def test_read_only_fields_not_writable():
    user = make_user(username="rotest", password="testpass123")
    profile = user.profile

    s = ProfileSerializer(
        profile,
        data={"is_admin": True, "is_member": True, "active": False, "name": "Allowed"},
        partial=True,
    )
    assert s.is_valid(), s.errors
    assert "is_admin" not in s.validated_data
    assert "is_member" not in s.validated_data
    assert "active" not in s.validated_data
    assert "name" in s.validated_data


@pytest.mark.django_db
def test_name_is_writable():
    user = make_user(username="nametest", password="testpass123")
    profile = user.profile

    s = ProfileSerializer(profile, data={"name": "New Name"}, partial=True)
    assert s.is_valid(), s.errors
    s.save()

    profile.refresh_from_db()
    assert profile.name == "New Name"
