from typing import IO, Protocol
from uuid import UUID

from features.members.dtos import (
    BirthdayDTO,
    ChangeLogEntryDTO,
    MemberCreateDTO,
    MemberDTO,
    MemberFieldChange,
    MemberOptionsDTO,
    MemberPatchDTO,
    MemberRecordDTO,
    MemberSummaryDTO,
    NamedRefDTO,
)


class MemberRepository(Protocol):
    """Contract for member persistence operations."""

    def list_active_members(self) -> list[MemberDTO]: ...

    def list_birthdays_by_month_range(
        self, start_month: int, end_month: int
    ) -> list[BirthdayDTO]: ...


class MemberRosterRepository(Protocol):
    """Leader-side member persistence: every record, valid or not.

    Never writes photo files; it only stores the name ``MemberPhotoStorage`` returned.
    """

    def exists(self, member_id: int) -> bool: ...

    def list_members(self) -> list[MemberSummaryDTO]: ...

    def get_record(self, member_id: int) -> MemberRecordDTO | None: ...

    def get_options(self) -> MemberOptionsDTO: ...

    def find_status(self, status_id: int) -> NamedRefDTO | None: ...

    def find_role(self, role_id: int) -> NamedRefDTO | None: ...

    def find_ministries(self, ministry_ids: list[int]) -> list[NamedRefDTO]: ...

    def create(self, dto: MemberCreateDTO) -> int: ...

    def update(self, member_id: int, dto: MemberPatchDTO) -> None: ...

    def delete(self, member_id: int) -> None: ...

    def get_photo_name(self, member_id: int) -> str | None: ...

    def set_photo_name(self, member_id: int, name: str | None) -> None: ...


class MemberChangeLogRepository(Protocol):
    """Edit history persistence. Writes happen inside the caller's transaction."""

    def add_entries(
        self, member_id: int, editor_id: UUID | None, changes: list[MemberFieldChange]
    ) -> None: ...

    def list_for_member(self, member_id: int) -> list[ChangeLogEntryDTO]: ...


class MemberPhotoStorage(Protocol):
    """Member photo files. Names are random; no member data ever goes into a path."""

    def save(self, extension: str, upload: IO[bytes]) -> str: ...

    def delete(self, name: str) -> None: ...
