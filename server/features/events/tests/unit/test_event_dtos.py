from datetime import date

import pytest
from pydantic import ValidationError

from features.events.domain.event_enums import EventVisibility
from features.events.dtos import EventCreateDTO, EventPatchDTO

NOV_14 = date(2026, 11, 14)
NOV_16 = date(2026, 11, 16)


class TestCreate:
    def test_text_is_trimmed_and_blank_becomes_none(self) -> None:
        dto = EventCreateDTO(
            title="  Retiro ", start_date=NOV_14, location="   ", description=" Três dias "
        )

        assert (dto.title, dto.location, dto.description) == ("Retiro", None, "Três dias")

    def test_visibility_defaults_to_public(self) -> None:
        assert EventCreateDTO(title="Retiro", start_date=NOV_14).visibility is (
            EventVisibility.PUBLIC
        )

    @pytest.mark.parametrize("title", ["", "   "])
    def test_blank_title_is_refused(self, title: str) -> None:
        with pytest.raises(ValidationError):
            EventCreateDTO(title=title, start_date=NOV_14)


class TestPatch:
    def test_changes_are_only_the_sent_fields(self) -> None:
        assert EventPatchDTO(location=" ", end_date=None).changes() == {
            "location": None,
            "end_date": None,
        }

    def test_blank_title_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            EventPatchDTO(title=" ")

    @pytest.mark.parametrize(
        ("patch", "expected"),
        [
            (EventPatchDTO(), (NOV_14, NOV_16)),
            (EventPatchDTO(end_date=None), (NOV_14, None)),
            (EventPatchDTO(start_date=date(2026, 11, 15)), (date(2026, 11, 15), NOV_16)),
        ],
    )
    def test_resulting_dates(
        self, patch: EventPatchDTO, expected: tuple[date, date | None]
    ) -> None:
        assert patch.resulting_dates(NOV_14, NOV_16) == expected
