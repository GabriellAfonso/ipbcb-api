from collections.abc import Collection, Mapping
from types import MappingProxyType
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.views import APIView

from config.di import Container
from core.application.access_service import AccessService
from core.application.worship_access_service import WorshipAccessService
from core.application.dtos.access_dtos import AccessGrantsDTO
from core.domain.access import Level, Scope, required_level, validate_overrides
from core.domain.exceptions import NotWorshipMemberError


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


@inject
def _grants_for(
    user_id: UUID, access_service: AccessService = Provide[Container.access_service]
) -> AccessGrantsDTO:
    # Module level on purpose: dependency-injector wires the functions a module holds when the
    # container is wired. A method of a class built later by ``scope_permission`` would never be.
    return access_service.grants_for(user_id)


@inject
def _is_worship_member(
    user_id: UUID,
    worship_access_service: WorshipAccessService = Provide[Container.worship_access_service],
) -> bool:
    # Module level for the same wiring reason as ``_grants_for``.
    return worship_access_service.is_worship_member(user_id)


class IsWorshipMember(permissions.BasePermission):
    """Only users in the worship ministry ("Louvor"). Not a management gate: it grants no scope
    level and reads no role — the band reads the current setlist with it whatever their roles
    (specs/017-sunday-setlist-push R-02).
    """

    message = NotWorshipMemberError().args[0]

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not (request.user and request.user.is_authenticated):
            return False
        return _is_worship_member(request.user.pk)


def scope_permission(
    scope: Scope,
    overrides: Mapping[str, Level] | None = None,
    *,
    lowered: Collection[str] = frozenset(),
) -> type[permissions.BasePermission]:
    """Permission class requiring a level on ``scope``: by method (GET view, POST/PUT/PATCH
    manage, DELETE owner) unless ``overrides`` raises it. An override below the default raises
    ``ValueError`` here, at import, unless its method is in ``lowered`` — an exception that must
    be listed in specs/012-feature-role-permissions/spec.md (Lowered overrides).

    >>> permission_classes = [IsAuthenticated, scope_permission(Scope.MEMBERS)]
    >>> scope_permission(Scope.REPORTS_HYMNAL_HISTORY, {"PATCH": Level.OWNER})
    """
    frozen_overrides = MappingProxyType(dict(overrides or {}))
    validate_overrides(frozen_overrides, lowered)

    class ScopePermission(permissions.BasePermission):
        message = "Você não tem permissão para esta ação."

        def has_permission(self, request: Request, view: APIView) -> bool:
            if not (request.user and request.user.is_authenticated):
                return False
            level = required_level(request.method or "", frozen_overrides)
            return _grants_for(request.user.pk).allows(scope, level)

    ScopePermission.__name__ = ScopePermission.__qualname__ = f"ScopePermission_{scope.name}"
    return ScopePermission
