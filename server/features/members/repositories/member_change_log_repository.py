from typing import Any
from uuid import UUID

from features.members.dtos import ChangeLogEditorDTO, ChangeLogEntryDTO, MemberFieldChange
from features.members.models.member_change_log import MemberChangeLog

_ENTRY_COLUMNS = (
    "id",
    "field",
    "old_value",
    "new_value",
    "changed_at",
    "editor_id",
    "editor__username",
    # An ORM path, not an import: the members feature does not import accounts
    # (constitution, Architecture). Profile.name is the name the app shows for a user.
    "editor__profile__name",
)


class MemberChangeLogRepositoryImpl:
    """Member edit history using Django ORM."""

    def add_entries(
        self, member_id: int, editor_id: UUID | None, changes: list[MemberFieldChange]
    ) -> None:
        """Insert all ``changes`` in one query.

        >>> repo.add_entries(12, editor_id, [MemberFieldChange(field="gender", ...)])
        """
        MemberChangeLog.objects.bulk_create(
            MemberChangeLog(
                member_id=member_id,
                editor_id=editor_id,
                field=change.field,
                old_value=change.old_value,
                new_value=change.new_value,
            )
            for change in changes
        )

    def list_for_member(self, member_id: int) -> list[ChangeLogEntryDTO]:
        """Entries for ``member_id``, newest first, in one query.

        >>> repo.list_for_member(12)
        [ChangeLogEntryDTO(id=40, field='ministries', ...), ...]
        """
        rows = MemberChangeLog.objects.filter(member_id=member_id).values(*_ENTRY_COLUMNS)
        return [_to_entry(row) for row in rows]


def _to_entry(row: dict[str, Any]) -> ChangeLogEntryDTO:
    return ChangeLogEntryDTO(
        id=row["id"],
        editor=_to_editor(row),
        field=row["field"],
        old_value=row["old_value"],
        new_value=row["new_value"],
        changed_at=row["changed_at"],
    )


def _to_editor(row: dict[str, Any]) -> ChangeLogEditorDTO | None:
    if row["editor_id"] is None:
        return None
    name = row["editor__profile__name"] or row["editor__username"]
    return ChangeLogEditorDTO(id=str(row["editor_id"]), name=name)
