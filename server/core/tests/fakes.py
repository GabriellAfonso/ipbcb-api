from uuid import UUID

from core.application.dtos.access_dtos import RoleGrantRowsDTO


class FakeRoleGrantRepository:
    """In-memory ``RoleGrantRepository``: every user holds the same fixed rows.

    >>> FakeRoleGrantRepository(["leader"], ["members__manage"]).role_grants(uuid4()).role_names
    ['leader']
    """

    def __init__(self, role_names: list[str], codenames: list[str]) -> None:
        self._rows = RoleGrantRowsDTO(role_names=role_names, codenames=codenames)
        self.calls: list[UUID] = []

    def role_grants(self, user_id: UUID) -> RoleGrantRowsDTO:
        self.calls.append(user_id)
        return self._rows
