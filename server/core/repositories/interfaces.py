from typing import Protocol
from uuid import UUID

from core.application.dtos.access_dtos import RoleGrantRowsDTO


class RoleGrantRepository(Protocol):
    """Contract for reading which panel roles a user holds and what those roles grant."""

    def role_grants(self, user_id: UUID) -> RoleGrantRowsDTO: ...
