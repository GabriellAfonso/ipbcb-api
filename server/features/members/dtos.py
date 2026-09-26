from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from core.application.dtos.strict_base import StrictBaseModel

Gender = Literal["M", "F"]


class MemberDTO(BaseModel):
    id: int
    name: str


class BirthdayDTO(BaseModel):
    name: str
    gender: str | None
    birth_month: int
    birth_day: int


class NamedRefDTO(BaseModel):
    """A status, role or ministry as the app shows it: id to send back, name to display."""

    id: int
    name: str


class MemberSummaryDTO(BaseModel):
    id: int
    name: str
    photo_path: str | None
    status: NamedRefDTO | None
    is_active: bool


class MemberRecordDTO(BaseModel):
    """The full member record. Also the snapshot the history diff compares."""

    id: int
    name: str
    first_name: str
    last_name: str
    birth_date: date | None
    gender: str | None
    status: NamedRefDTO | None
    role: NamedRefDTO | None
    ministries: list[NamedRefDTO]
    baptism_date: date | None
    is_active: bool
    photo_path: str | None
    created_at: datetime


class MemberCreateDTO(StrictBaseModel):
    name: str
    first_name: str = ""
    last_name: str = ""
    birth_date: date | None = None
    gender: Gender | None = None
    status_id: int | None = None
    role_id: int | None = None
    ministry_ids: list[int] = []
    baptism_date: date | None = None
    is_active: bool = True


class MemberPatchDTO(StrictBaseModel):
    """Partial edit. Only ``model_fields_set`` is applied: an absent field is left alone,
    a field sent as None is cleared."""

    name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    birth_date: date | None = None
    gender: Gender | None = None
    status_id: int | None = None
    role_id: int | None = None
    ministry_ids: list[int] | None = None
    baptism_date: date | None = None
    is_active: bool | None = None


class MemberFieldChange(BaseModel):
    field: str
    old_value: str | None
    new_value: str | None


class ChangeLogEditorDTO(BaseModel):
    id: str
    name: str


class ChangeLogEntryDTO(BaseModel):
    id: int
    editor: ChangeLogEditorDTO | None
    field: str
    old_value: str | None
    new_value: str | None
    changed_at: datetime


class MemberOptionsDTO(BaseModel):
    statuses: list[NamedRefDTO]
    roles: list[NamedRefDTO]
    ministries: list[NamedRefDTO]
