"""History rules for member edits: which fields are tracked and how values read as text.

Pure functions, no I/O. The services snapshot a ``MemberRecordDTO`` before and after a
write and diff the two, so a field sent with its current value produces no entry and
names are the ones stored at edit time (specs/010-members-management/research.md R-02).
"""

from datetime import date
from typing import Final

from features.members.dtos import MemberFieldChange, MemberRecordDTO, NamedRefDTO

HistoryValue = str | bool | date | NamedRefDTO | list[NamedRefDTO] | None

# MemberRecordDTO attribute names; also the "field" stored in each history entry.
HISTORY_FIELDS: Final = (
    "name",
    "first_name",
    "last_name",
    "birth_date",
    "gender",
    "status",
    "role",
    "ministries",
    "baptism_date",
    "is_active",
)
CREATED_FIELD: Final = "created"
PHOTO_FIELD: Final = "photo"
PHOTO_CHANGED: Final = "photo changed"
PHOTO_REMOVED: Final = "photo removed"


def render_history_value(value: HistoryValue) -> str | None:
    """Text stored in the history for ``value``; None for an empty value.

    >>> render_history_value([NamedRefDTO(id=2, name="B"), NamedRefDTO(id=1, name="A")])
    'A, B'
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, NamedRefDTO):
        return value.name
    if isinstance(value, list):
        return ", ".join(sorted(ref.name for ref in value)) or None
    return value or None


def diff_member_records(before: MemberRecordDTO, after: MemberRecordDTO) -> list[MemberFieldChange]:
    """One change per tracked field whose rendered value differs, in HISTORY_FIELDS order.

    >>> diff_member_records(record, record.model_copy(update={"gender": "M"}))
    [MemberFieldChange(field='gender', old_value='F', new_value='M')]
    """
    changes = []
    for field in HISTORY_FIELDS:
        old_value = render_history_value(getattr(before, field))
        new_value = render_history_value(getattr(after, field))
        if old_value != new_value:
            changes.append(MemberFieldChange(field=field, old_value=old_value, new_value=new_value))
    return changes
