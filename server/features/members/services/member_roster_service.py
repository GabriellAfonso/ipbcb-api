from datetime import date
from functools import partial
from uuid import UUID

from django.db import transaction

from core.domain.exceptions import MemberNotFoundError, ValidationError
from core.time.clock import Clock
from features.members.domain.member_changes import CREATED_FIELD, diff_member_records
from features.members.domain.member_dates import BirthDateParts, validate_member_date_parts
from features.members.dtos import (
    MemberCreateDTO,
    MemberFieldChange,
    MemberOptionsDTO,
    MemberPatchDTO,
    MemberRecordDTO,
    MemberSummaryDTO,
)
from features.members.repositories.interfaces import (
    MemberChangeLogRepository,
    MemberPhotoStorage,
    MemberRosterRepository,
)
from features.members.services.member_write_log import log_member_write


class MemberRosterService:
    """Leader use cases on the membership roll: read, create, edit, delete.

    Every write and its history entries commit together (``transaction.atomic``); files are
    removed only after the commit (specs/010-members-management/research.md R-01, R-05).
    """

    def __init__(
        self,
        roster_repository: MemberRosterRepository,
        change_log_repository: MemberChangeLogRepository,
        photo_storage: MemberPhotoStorage,
        clock: Clock,
    ) -> None:
        self._roster = roster_repository
        self._change_log = change_log_repository
        self._photos = photo_storage
        self._clock = clock

    def list_members(self) -> list[MemberSummaryDTO]:
        """Every member, valid profile or not, ordered by name.

        >>> service.list_members()
        [MemberSummaryDTO(id=12, name='Ana Souza', ...), ...]
        """
        return self._roster.list_members()

    def get_member(self, member_id: int) -> MemberRecordDTO:
        """The full record, or ``MemberNotFoundError``.

        >>> service.get_member(12).name
        'Ana Souza'
        """
        record = self._roster.get_record(member_id)
        if record is None:
            raise MemberNotFoundError(member_id)
        return record

    def get_options(self) -> MemberOptionsDTO:
        """Statuses, roles and ministries for the app's pickers.

        >>> service.get_options().statuses
        [NamedRefDTO(id=1, name='Comungante'), ...]
        """
        return self._roster.get_options()

    def create_member(self, dto: MemberCreateDTO, editor_id: UUID | None) -> MemberRecordDTO:
        """Store a new member and one ``created`` history entry.

        >>> service.create_member(MemberCreateDTO(name="Ana Souza"), leader_id).id
        12
        """
        self._check_references(dto.status_id, dto.role_id, dto.ministry_ids)
        birth = BirthDateParts(dto.birth_day, dto.birth_month, dto.birth_year)
        validate_member_date_parts(birth, dto.baptism_date, self._today())
        created = MemberFieldChange(field=CREATED_FIELD, old_value=None, new_value=None)
        with transaction.atomic():
            member_id = self._roster.create(dto)
            self._change_log.add_entries(member_id, editor_id, [created])
        log_member_write("member_created", member_id, editor_id, changed_fields=1)
        return self.get_member(member_id)

    def update_member(
        self, member_id: int, dto: MemberPatchDTO, editor_id: UUID | None
    ) -> MemberRecordDTO:
        """Apply the fields sent and write one history entry per value that changed.

        >>> service.update_member(12, MemberPatchDTO(gender="M"), leader_id).gender
        'M'
        """
        before = self.get_member(member_id)
        self._check_patch(dto, before)
        with transaction.atomic():
            self._roster.update(member_id, dto)
            after = self.get_member(member_id)
            changes = diff_member_records(before, after)
            self._change_log.add_entries(member_id, editor_id, changes)
        log_member_write("member_updated", member_id, editor_id, changed_fields=len(changes))
        return after

    def delete_member(self, member_id: int, editor_id: UUID | None) -> None:
        """Delete the member and its history; its photo file goes after the commit.

        >>> service.delete_member(12, leader_id)
        """
        if not self._roster.exists(member_id):
            raise MemberNotFoundError(member_id)
        photo_name = self._roster.get_photo_name(member_id)
        with transaction.atomic():
            self._roster.delete(member_id)
            if photo_name:
                transaction.on_commit(partial(self._photos.delete, photo_name), robust=True)
        log_member_write("member_deleted", member_id, editor_id, changed_fields=0)

    def _check_patch(self, dto: MemberPatchDTO, before: MemberRecordDTO) -> None:
        sent = dto.model_fields_set
        if "name" in sent and not (dto.name or "").strip():
            raise ValidationError(f"O nome não pode ficar vazio; recebido: {dto.name!r}.")
        self._check_references(
            dto.status_id if "status_id" in sent else None,
            dto.role_id if "role_id" in sent else None,
            dto.ministry_ids if "ministry_ids" in sent else None,
        )
        baptism_date = dto.baptism_date if "baptism_date" in sent else before.baptism_date
        validate_member_date_parts(_merged_birth(dto, before), baptism_date, self._today())

    def _check_references(
        self, status_id: int | None, role_id: int | None, ministry_ids: list[int] | None
    ) -> None:
        if status_id is not None and self._roster.find_status(status_id) is None:
            raise ValidationError(f"Situação não encontrada: status_id={status_id}.")
        if role_id is not None and self._roster.find_role(role_id) is None:
            raise ValidationError(f"Cargo não encontrado: role_id={role_id}.")
        if ministry_ids:
            self._check_ministries(ministry_ids)

    def _check_ministries(self, ministry_ids: list[int]) -> None:
        found = {ministry.id for ministry in self._roster.find_ministries(ministry_ids)}
        missing = sorted(set(ministry_ids) - found)
        if missing:
            raise ValidationError(f"Ministérios não encontrados: ministry_ids={missing}.")

    def _today(self) -> date:
        return self._clock.now().date()


def _merged_birth(dto: MemberPatchDTO, before: MemberRecordDTO) -> BirthDateParts:
    """The birth parts as they would be after the patch: each part sent wins, else stored.

    >>> _merged_birth(MemberPatchDTO(birth_day=31), stored_with_month_4)
    BirthDateParts(day=31, month=4, year=None)
    """
    sent = dto.model_fields_set
    parts = [
        getattr(dto if name in sent else before, name)
        for name in ("birth_day", "birth_month", "birth_year")
    ]
    return BirthDateParts(*parts)
