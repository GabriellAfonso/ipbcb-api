from collections.abc import Collection, Iterable, Sequence
from uuid import UUID

from core.application.dtos.access_dtos import RoleGrantRowsDTO
from core.application.dtos.push_dtos import PushMessage, PushSendReport
from core.domain.access import Level, Scope


class FakeRoleGrantRepository:
    """In-memory ``RoleGrantRepository``: every user holds the same fixed rows.

    ``level_holders`` answers ``user_ids_with_level`` for any scope and level.

    >>> FakeRoleGrantRepository(["leader"], ["members__manage"]).role_grants(uuid4()).role_names
    ['leader']
    """

    def __init__(
        self,
        role_names: list[str],
        codenames: list[str],
        level_holders: set[UUID] | None = None,
    ) -> None:
        self._rows = RoleGrantRowsDTO(role_names=role_names, codenames=codenames)
        self._level_holders = set(level_holders or set())
        self.calls: list[UUID] = []

    def role_grants(self, user_id: UUID) -> RoleGrantRowsDTO:
        self.calls.append(user_id)
        return self._rows

    def user_ids_with_level(self, scope: Scope, level: Level) -> set[UUID]:
        return set(self._level_holders)


class FakeWorshipMembership:
    """In-memory ``WorshipMembershipRepository``: a fixed set of worship member ids.

    >>> FakeWorshipMembership({leader_id}).is_worship_member(leader_id)
    True
    """

    def __init__(self, member_ids: set[UUID] | None = None, ministry_exists: bool = True) -> None:
        self.member_ids = set(member_ids or set())
        self.ministry_exists = ministry_exists

    def is_worship_member(self, user_id: UUID) -> bool:
        return user_id in self.member_ids

    def worship_member_user_ids(self) -> set[UUID]:
        return set(self.member_ids)

    def worship_ministry_exists(self) -> bool:
        return self.ministry_exists


class FakeDeviceTokenRepository:
    """In-memory ``DeviceTokenRepository``: token -> owner.

    >>> repo = FakeDeviceTokenRepository({"t1": ana_id}); repo.tokens_for([ana_id])
    ['t1']
    """

    def __init__(self, owners: dict[str, UUID] | None = None) -> None:
        self.owners: dict[str, UUID] = dict(owners or {})

    def register(self, user_id: UUID, token: str) -> None:
        self.owners[token] = user_id

    def unregister(self, user_id: UUID, token: str) -> None:
        if self.owners.get(token) == user_id:
            del self.owners[token]

    def tokens_for(self, user_ids: Collection[UUID]) -> list[str]:
        wanted = set(user_ids)
        return sorted(token for token, owner in self.owners.items() if owner in wanted)

    def delete_tokens(self, tokens: Iterable[str]) -> int:
        removed = [token for token in set(tokens) if self.owners.pop(token, None) is not None]
        return len(removed)


class FakePushSender:
    """Records every send. Tokens in ``invalid`` come back as unregistered; ``raises`` makes the
    call blow up, as a sender bug would; ``report`` overrides the answer entirely.

    >>> sender = FakePushSender(invalid={"old"}); sender.send(["new", "old"], message).sent
    1
    """

    def __init__(
        self,
        invalid: set[str] | None = None,
        raises: Exception | None = None,
        report: PushSendReport | None = None,
    ) -> None:
        self.invalid = set(invalid or set())
        self.raises = raises
        self.report = report
        self.calls: list[tuple[list[str], PushMessage]] = []

    def send(self, tokens: Sequence[str], message: PushMessage) -> PushSendReport:
        self.calls.append((list(tokens), message))
        if self.raises is not None:
            raise self.raises
        if self.report is not None:
            return self.report
        invalid = [token for token in tokens if token in self.invalid]
        return PushSendReport(sent=len(tokens) - len(invalid), invalid_tokens=invalid)
