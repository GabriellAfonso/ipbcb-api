from collections.abc import Collection, Iterable
from typing import Protocol
from uuid import UUID

from core.application.dtos.access_dtos import RoleGrantRowsDTO
from core.domain.access import Level, Scope


class RoleGrantRepository(Protocol):
    """Contract for reading which panel roles a user holds and what those roles grant."""

    def role_grants(self, user_id: UUID) -> RoleGrantRowsDTO: ...

    def user_ids_with_level(self, scope: Scope, level: Level) -> set[UUID]: ...


class WorshipMembershipRepository(Protocol):
    """Contract for "is this user in the worship ministry" (specs/017-sunday-setlist-push R-03)."""

    def is_worship_member(self, user_id: UUID) -> bool: ...

    def worship_member_user_ids(self) -> set[UUID]: ...

    def worship_ministry_exists(self) -> bool: ...


class DeviceTokenRepository(Protocol):
    """Contract for the push registration tokens of each user's devices."""

    def register(self, user_id: UUID, token: str) -> None: ...

    def unregister(self, user_id: UUID, token: str) -> None: ...

    def tokens_for(self, user_ids: Collection[UUID]) -> list[str]: ...

    def delete_tokens(self, tokens: Iterable[str]) -> int: ...
