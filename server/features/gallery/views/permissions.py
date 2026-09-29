from rest_framework.permissions import BasePermission, IsAuthenticated

from core.domain.access import Scope
from core.http.permissions import IsMemberUser, scope_permission

_READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_GalleryWrite = scope_permission(Scope.GALLERY)


def member_read_gallery_write_permissions(method: str) -> list[BasePermission]:
    """Permissions for a route that serves a member read and a gallery write on one URL
    (``/api/albums/``, ``/api/photos/``). DRF binds permissions per view, and
    ``scope_permission`` alone would ask ``view`` on ``gallery`` for the read, locking plain
    members out (specs/013-gallery-write-api research R-07).

    >>> member_read_gallery_write_permissions("GET")
    [<IsMemberUser>]
    """
    if method.upper() in _READ_METHODS:
        return [IsMemberUser()]
    return [IsAuthenticated(), _GalleryWrite()]
