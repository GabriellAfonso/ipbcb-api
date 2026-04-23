from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.views import APIView


class IsMemberUser(permissions.BasePermission):
    """
    Permite acesso apenas a usuários que possuem um perfil com is_member = True.
    """

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user.profile, "is_member", False)
        )


class IsAdminUser(permissions.BasePermission):
    """
    Permite acesso apenas a usuários que possuem um perfil com is_admin = True.
    """

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user.profile, "is_admin", False)
        )
