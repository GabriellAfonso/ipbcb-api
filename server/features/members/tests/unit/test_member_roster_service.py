"""MemberRosterService with named fakes. ``django_db`` only because the service opens
``transaction.atomic`` (research R-01); no ORM model is touched."""

import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import date
from uuid import UUID, uuid4

import pytest

from core.domain.exceptions import MemberNotFoundError, ValidationError
from features.members.dtos import (
    MemberCreateDTO,
    MemberFieldChange,
    MemberOptionsDTO,
    MemberPatchDTO,
    NamedRefDTO,
)
from features.members.services.member_roster_service import MemberRosterService
from features.members.tests.fakes import (
    FakeMemberChangeLogRepository,
    FakeMemberPhotoStorage,
    FakeMemberRosterRepository,
    FixedClock,
)

CaptureOnCommit = Callable[..., AbstractContextManager[list[Callable[[], object]]]]

COMUNGANTE = NamedRefDTO(id=1, name="Comungante")
DIACONO = NamedRefDTO(id=5, name="Diácono")
LOUVOR = NamedRefDTO(id=2, name="Louvor")
RECEPCAO = NamedRefDTO(id=3, name="Recepção")
ACAO = NamedRefDTO(id=4, name="Ação social")
OPTIONS = MemberOptionsDTO(
    statuses=[COMUNGANTE], roles=[DIACONO], ministries=[ACAO, LOUVOR, RECEPCAO]
)
EDITOR: UUID = uuid4()
ALLOWED_LOG_KEYS = {"member_id", "editor_id", "changed_fields"}


class Harness:
    def __init__(self) -> None:
        self.roster = FakeMemberRosterRepository(OPTIONS)
        self.change_log = FakeMemberChangeLogRepository()
        self.photos = FakeMemberPhotoStorage()
        self.service = MemberRosterService(
            roster_repository=self.roster,
            change_log_repository=self.change_log,
            photo_storage=self.photos,
            clock=FixedClock(date(2026, 9, 25)),
        )


@pytest.fixture
def h() -> Harness:
    return Harness()


def _member_log_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.getMessage().startswith("member_")]


def _extra_keys(record: logging.LogRecord) -> set[str]:
    """Keys the service added. request_id comes from the logging filter (feature 002)."""
    standard = logging.LogRecord("", 0, "", 0, "", None, None).__dict__.keys()
    return set(record.__dict__) - set(standard) - {"message", "asctime", "request_id"}


class TestRead:
    def test_list_members_returns_every_record(self, h: Harness) -> None:
        h.roster.add("Bruno", is_active=False)
        h.roster.add("Ana")

        names = [m.name for m in h.service.list_members()]

        assert names == ["Ana", "Bruno"]

    def test_get_member_unknown_id_raises(self, h: Harness) -> None:
        with pytest.raises(MemberNotFoundError, match="99"):
            h.service.get_member(99)

    def test_get_options_comes_from_the_repository(self, h: Harness) -> None:
        assert h.service.get_options() == OPTIONS


@pytest.mark.django_db
class TestCreate:
    def test_writes_one_created_entry_with_the_editor(self, h: Harness) -> None:
        record = h.service.create_member(MemberCreateDTO(name="Ana Souza"), EDITOR)

        assert h.change_log.calls == [
            (
                record.id,
                EDITOR,
                [MemberFieldChange(field="created", old_value=None, new_value=None)],
            )
        ]

    def test_stores_references(self, h: Harness) -> None:
        dto = MemberCreateDTO(name="Ana", status_id=1, role_id=5, ministry_ids=[3, 2])

        record = h.service.create_member(dto, EDITOR)

        assert record.status == COMUNGANTE
        assert record.role == DIACONO
        assert {m.id for m in record.ministries} == {2, 3}

    @pytest.mark.parametrize(
        ("dto", "message"),
        [
            (MemberCreateDTO(name="Ana", status_id=77), "status_id=77"),
            (MemberCreateDTO(name="Ana", role_id=78), "role_id=78"),
            (MemberCreateDTO(name="Ana", ministry_ids=[2, 80, 81]), r"\[80, 81\]"),
            (MemberCreateDTO(name="Ana", birth_year=2027), "birth_year=2027"),
            (MemberCreateDTO(name="Ana", birth_day=12), "birth_day=12, birth_month=None"),
        ],
    )
    def test_invalid_input_stores_nothing(
        self, h: Harness, dto: MemberCreateDTO, message: str
    ) -> None:
        with pytest.raises(ValidationError, match=message):
            h.service.create_member(dto, EDITOR)

        assert h.roster.records == {}
        assert h.change_log.calls == []

    def test_logs_ids_only(self, h: Harness, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO, logger="features.members")

        h.service.create_member(MemberCreateDTO(name="Maria Sigilo"), EDITOR)

        (record,) = _member_log_records(caplog)
        assert record.getMessage() == "member_created"
        assert _extra_keys(record) == ALLOWED_LOG_KEYS
        assert "Maria" not in str(record.__dict__)


@pytest.mark.django_db
class TestUpdate:
    def test_one_entry_per_changed_field(self, h: Harness) -> None:
        member = h.roster.add("Ana", birth_day=2, birth_month=4, birth_year=1990)

        h.service.update_member(member.id, MemberPatchDTO(status_id=1, birth_year=1991), EDITOR)

        assert h.change_log.changes == [
            MemberFieldChange(field="birth_year", old_value="1990", new_value="1991"),
            MemberFieldChange(field="status", old_value=None, new_value="Comungante"),
        ]

    def test_unchanged_values_write_no_entry(self, h: Harness) -> None:
        member = h.roster.add("Ana", gender="F")

        h.service.update_member(member.id, MemberPatchDTO(name="Ana", gender="F"), EDITOR)

        assert h.change_log.changes == []

    def test_ministries_are_one_entry_with_full_lists(self, h: Harness) -> None:
        member = h.roster.add("Ana", ministries=[LOUVOR, ACAO])

        h.service.update_member(member.id, MemberPatchDTO(ministry_ids=[2, 3]), EDITOR)

        assert h.change_log.changes == [
            MemberFieldChange(
                field="ministries", old_value="Ação social, Louvor", new_value="Louvor, Recepção"
            )
        ]

    def test_null_clears_status(self, h: Harness) -> None:
        member = h.roster.add("Ana", status=COMUNGANTE)

        record = h.service.update_member(member.id, MemberPatchDTO(status_id=None), EDITOR)

        assert record.status is None

    def test_absent_field_is_left_alone(self, h: Harness) -> None:
        member = h.roster.add("Ana", status=COMUNGANTE)

        record = h.service.update_member(member.id, MemberPatchDTO(gender="F"), EDITOR)

        assert record.status == COMUNGANTE

    def test_baptism_checked_against_stored_birth_year(self, h: Harness) -> None:
        member = h.roster.add("Ana", birth_year=2000)

        with pytest.raises(ValidationError, match="1999-05-01"):
            h.service.update_member(
                member.id, MemberPatchDTO(baptism_date=date(1999, 5, 1)), EDITOR
            )
        assert h.change_log.calls == []

    @pytest.mark.parametrize(
        ("stored", "patch", "message"),
        [
            ({"birth_day": 1, "birth_month": 4}, MemberPatchDTO(birth_day=31), "31/04"),
            (
                {"birth_day": 12, "birth_month": 3},
                MemberPatchDTO(birth_month=None),
                "birth_day=12, birth_month=None",
            ),
            ({"birth_day": 29, "birth_month": 2}, MemberPatchDTO(birth_year=1990), "29/02/1990"),
        ],
    )
    def test_birth_parts_checked_merged_with_stored(
        self, h: Harness, stored: dict[str, int], patch: MemberPatchDTO, message: str
    ) -> None:
        # Spec 011 FR-006: parts not sent come from the stored record before validating.
        member = h.roster.add("Ana", **stored)

        with pytest.raises(ValidationError, match=message):
            h.service.update_member(member.id, patch, EDITOR)
        assert h.change_log.calls == []

    def test_blank_name_rejected(self, h: Harness) -> None:
        member = h.roster.add("Ana")

        with pytest.raises(ValidationError, match="nome"):
            h.service.update_member(member.id, MemberPatchDTO(name="  "), EDITOR)

    def test_unknown_member_raises(self, h: Harness) -> None:
        with pytest.raises(MemberNotFoundError):
            h.service.update_member(42, MemberPatchDTO(gender="M"), EDITOR)

    def test_history_failure_propagates(self, h: Harness) -> None:
        member = h.roster.add("Ana")
        h.change_log.fail_on_add = True

        with pytest.raises(RuntimeError):
            h.service.update_member(member.id, MemberPatchDTO(gender="M"), EDITOR)

    def test_logs_change_count_only(self, h: Harness, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO, logger="features.members")
        member = h.roster.add("Maria Sigilo")

        h.service.update_member(member.id, MemberPatchDTO(gender="F", role_id=5), EDITOR)

        (record,) = _member_log_records(caplog)
        assert record.getMessage() == "member_updated"
        assert _extra_keys(record) == ALLOWED_LOG_KEYS
        assert record.__dict__["changed_fields"] == 2


@pytest.mark.django_db
class TestDelete:
    def test_photo_deleted_only_on_commit(
        self, h: Harness, django_capture_on_commit_callbacks: CaptureOnCommit
    ) -> None:
        member = h.roster.add("Ana")
        h.roster.set_photo_name(member.id, "members/old.jpg")

        with django_capture_on_commit_callbacks() as callbacks:
            h.service.delete_member(member.id, EDITOR)
            assert h.photos.deleted == []

        assert len(callbacks) == 1
        callbacks[0]()
        assert h.photos.deleted == ["members/old.jpg"]
        assert h.roster.deleted_ids == [member.id]

    def test_without_photo_schedules_nothing(
        self, h: Harness, django_capture_on_commit_callbacks: CaptureOnCommit
    ) -> None:
        member = h.roster.add("Ana")

        with django_capture_on_commit_callbacks() as callbacks:
            h.service.delete_member(member.id, EDITOR)

        assert callbacks == []

    def test_unknown_member_raises(self, h: Harness) -> None:
        with pytest.raises(MemberNotFoundError):
            h.service.delete_member(42, EDITOR)

    def test_logs_ids_only(self, h: Harness, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO, logger="features.members")
        member = h.roster.add("Maria Sigilo")

        h.service.delete_member(member.id, EDITOR)

        (record,) = _member_log_records(caplog)
        assert record.getMessage() == "member_deleted"
        assert _extra_keys(record) == ALLOWED_LOG_KEYS
