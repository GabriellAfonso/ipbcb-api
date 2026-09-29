import pytest
from rest_framework.permissions import IsAuthenticated

from core.http.permissions import IsMemberUser
from features.gallery.views.permissions import member_read_gallery_write_permissions


class TestMemberReadGalleryWritePermissions:
    @pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS", "get"])
    def test_reads_need_membership_only(self, method: str) -> None:
        permissions = member_read_gallery_write_permissions(method)

        assert [type(p) for p in permissions] == [IsMemberUser]

    @pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
    def test_writes_need_authentication_and_the_gallery_scope(self, method: str) -> None:
        permissions = member_read_gallery_write_permissions(method)

        assert isinstance(permissions[0], IsAuthenticated)
        assert type(permissions[1]).__name__ == "ScopePermission_GALLERY"
