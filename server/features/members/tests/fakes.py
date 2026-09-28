"""Named in-memory fakes for the members feature's ports (CLAUDE.md §10)."""

from collections.abc import Iterable
from datetime import date, datetime, timezone
from typing import IO
from uuid import UUID

from features.members.dtos import (
    ChangeLogEntryDTO,
    MemberCreateDTO,
    MemberFieldChange,
    MemberOptionsDTO,
    MemberPatchDTO,
    MemberRecordDTO,
    MemberSummaryDTO,
    NamedRefDTO,
)

FAKE_MEDIA_URL = "/media/"


class FakeMemberRosterRepository:
    """Members as ``MemberRecordDTO`` in a dict, with fixed statuses, roles and ministries."""

    def __init__(self, options: MemberOptionsDTO | None = None) -> None:
        self.options = options or MemberOptionsDTO(statuses=[], roles=[], ministries=[])
        self.records: dict[int, MemberRecordDTO] = {}
        self.photo_names: dict[int, str | None] = {}
        self.deleted_ids: list[int] = []
        self._next_id = 1

    def add(self, name: str = "Ana", **fields: object) -> MemberRecordDTO:
        record = MemberRecordDTO.model_validate({**_blank_record(self._next_id, name), **fields})
        self.records[record.id] = record
        self.photo_names[record.id] = None
        self._next_id += 1
        return record

    def exists(self, member_id: int) -> bool:
        return member_id in self.records

    def list_members(self) -> list[MemberSummaryDTO]:
        return [
            MemberSummaryDTO(
                id=r.id,
                name=r.name,
                photo_path=r.photo_path,
                status=r.status,
                is_active=r.is_active,
            )
            for r in sorted(self.records.values(), key=lambda r: r.name)
        ]

    def get_record(self, member_id: int) -> MemberRecordDTO | None:
        return self.records.get(member_id)

    def get_options(self) -> MemberOptionsDTO:
        return self.options

    def find_status(self, status_id: int) -> NamedRefDTO | None:
        return _find(self.options.statuses, status_id)

    def find_role(self, role_id: int) -> NamedRefDTO | None:
        return _find(self.options.roles, role_id)

    def find_ministries(self, ministry_ids: list[int]) -> list[NamedRefDTO]:
        return [m for m in self.options.ministries if m.id in ministry_ids]

    def create(self, dto: MemberCreateDTO) -> int:
        record = self.add(dto.name)
        self._apply(record.id, dto.model_dump(), dto.model_dump().keys())
        return record.id

    def update(self, member_id: int, dto: MemberPatchDTO) -> None:
        self._apply(member_id, dto.model_dump(), dto.model_fields_set)

    def delete(self, member_id: int) -> None:
        self.records.pop(member_id)
        self.deleted_ids.append(member_id)

    def get_photo_name(self, member_id: int) -> str | None:
        return self.photo_names.get(member_id)

    def set_photo_name(self, member_id: int, name: str | None) -> None:
        self.photo_names[member_id] = name
        path = f"{FAKE_MEDIA_URL}{name}" if name else None
        self.records[member_id] = self.records[member_id].model_copy(update={"photo_path": path})

    def _apply(self, member_id: int, values: dict[str, object], fields: Iterable[str]) -> None:
        update: dict[str, object] = {}
        for field in fields:
            update.update(self._translate(field, values[field]))
        self.records[member_id] = self.records[member_id].model_copy(update=update)

    def _translate(self, field: str, value: object) -> dict[str, object]:
        if field == "status_id":
            return {"status": _find(self.options.statuses, value)}
        if field == "role_id":
            return {"role": _find(self.options.roles, value)}
        if field == "ministry_ids":
            ids = value if isinstance(value, list) else []
            return {"ministries": self.find_ministries(ids)}
        return {field: value}


class FakeMemberChangeLogRepository:
    """Records ``add_entries`` calls; serves preset history entries."""

    def __init__(self, entries: list[ChangeLogEntryDTO] | None = None) -> None:
        self.calls: list[tuple[int, UUID | None, list[MemberFieldChange]]] = []
        self.entries = entries or []
        self.fail_on_add = False

    def add_entries(
        self, member_id: int, editor_id: UUID | None, changes: list[MemberFieldChange]
    ) -> None:
        if self.fail_on_add:
            raise RuntimeError(f"history write failed for member {member_id}")
        self.calls.append((member_id, editor_id, changes))

    def list_for_member(self, member_id: int) -> list[ChangeLogEntryDTO]:
        return self.entries

    @property
    def changes(self) -> list[MemberFieldChange]:
        return [change for _, _, changes in self.calls for change in changes]


class FakeMemberPhotoStorage:
    """Photo files in a dict; records saves and deletions."""

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.deleted: list[str] = []
        self._counter = 0

    def save(self, extension: str, upload: IO[bytes]) -> str:
        self._counter += 1
        name = f"members/fake{self._counter}.{extension}"
        self.files[name] = upload.read()
        return name

    def delete(self, name: str) -> None:
        self.files.pop(name, None)
        self.deleted.append(name)


class FixedClock:
    def __init__(self, today: date = date(2026, 9, 25)) -> None:
        self._now = datetime(today.year, today.month, today.day, 12, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self._now


def _find(refs: list[NamedRefDTO], ref_id: object) -> NamedRefDTO | None:
    return next((ref for ref in refs if ref.id == ref_id), None)


def _blank_record(member_id: int, name: str) -> dict[str, object]:
    return {
        "id": member_id,
        "name": name,
        "first_name": "",
        "last_name": "",
        "birth_day": None,
        "birth_month": None,
        "birth_year": None,
        "gender": None,
        "status": None,
        "role": None,
        "ministries": [],
        "baptism_date": None,
        "is_active": True,
        "photo_path": None,
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
