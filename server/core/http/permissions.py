from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.views import APIView


def _profile_of(request: Request) -> object | None:
    """The caller's Profile, or None when the row does not exist.

    ``request.user.profile`` raises ``RelatedObjectDoesNotExist`` for a user without a row.
    That exception subclasses ``AttributeError``, so ``getattr`` with a default absorbs it —
    but only if the lookup happens inside ``getattr``, not as its first argument.

    >>> getattr(_profile_of(request), "is_member", False)
    """
    return getattr(request.user, "profile", None)


class IsMemberUser(permissions.BasePermission):
    """
    Permite acesso apenas a usuários que possuem um perfil com is_member = True.
    """

    message = "Disponível apenas para membros."

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(_profile_of(request), "is_member", False)
        )


class IsAdminUser(permissions.BasePermission):
    """
    Permite acesso apenas a usuários que possuem um perfil com is_admin = True.
    """

    message = "Acesso restrito a administradores."

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(_profile_of(request), "is_admin", False)
        )
