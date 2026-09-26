from datetime import date, datetime, timezone

import pytest

from features.members.domain.member_changes import (
    HistoryValue,
    diff_member_records,
    render_history_value,
)
from features.members.dtos import MemberFieldChange, MemberRecordDTO, NamedRefDTO

ANA = NamedRefDTO(id=1, name="Ana")
LOUVOR = NamedRefDTO(id=2, name="Louvor")
RECEPCAO = NamedRefDTO(id=3, name="Recepção")
ACAO = NamedRefDTO(id=4, name="Ação social")


def _record(**overrides: object) -> MemberRecordDTO:
    fields: dict[str, object] = {
        "id": 1,
        "name": "Ana Souza",
        "first_name": "Ana",
        "last_name": "Souza",
        "birth_date": date(1990, 4, 2),
        "gender": "F",
        "status": None,
        "role": None,
        "ministries": [],
        "baptism_date": None,
        "is_active": True,
        "photo_path": None,
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    fields.update(overrides)
    return MemberRecordDTO.model_validate(fields)


class TestRenderHistoryValue:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (None, None),
            ("Ana", "Ana"),
            ("", None),
            (date(2005, 6, 12), "2005-06-12"),
            (True, "true"),
            (False, "false"),
            (ANA, "Ana"),
            ([], None),
            ([RECEPCAO, LOUVOR, ACAO], "Ação social, Louvor, Recepção"),
        ],
    )
    def test_renders_each_value_type(self, value: HistoryValue, expected: str | None) -> None:
        assert render_history_value(value) == expected


class TestDiffMemberRecords:
    def test_equal_records_produce_no_change(self) -> None:
        assert diff_member_records(_record(), _record()) == []

    def test_one_change_per_differing_field(self) -> None:
        before = _record()
        after = _record(status=ANA, birth_date=date(1991, 1, 1))

        changes = diff_member_records(before, after)

        assert changes == [
            MemberFieldChange(field="birth_date", old_value="1990-04-02", new_value="1991-01-01"),
            MemberFieldChange(field="status", old_value=None, new_value="Ana"),
        ]

    def test_ministries_change_is_one_entry_with_full_lists(self) -> None:
        before = _record(ministries=[LOUVOR, ACAO])
        after = _record(ministries=[LOUVOR, RECEPCAO])

        changes = diff_member_records(before, after)

        assert changes == [
            MemberFieldChange(
                field="ministries",
                old_value="Ação social, Louvor",
                new_value="Louvor, Recepção",
            )
        ]

    def test_ministries_order_alone_is_not_a_change(self) -> None:
        before = _record(ministries=[LOUVOR, ACAO])
        after = _record(ministries=[ACAO, LOUVOR])

        assert diff_member_records(before, after) == []

    def test_blank_and_none_are_the_same_value(self) -> None:
        assert diff_member_records(_record(first_name=""), _record(first_name="")) == []

    def test_photo_and_created_at_are_not_diffed(self) -> None:
        after = _record(photo_path="/ipbcb/media/members/x.png")

        assert diff_member_records(_record(), after) == []
