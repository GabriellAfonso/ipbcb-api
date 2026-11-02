import pytest
from pydantic import ValidationError

from features.songs.dtos import ChordChartChangesInput


class TestAcceptedChanges:
    def test_dump_holds_only_the_keys_sent(self) -> None:
        changes = ChordChartChangesInput.model_validate({"tone": " G "})
        assert changes.model_dump(exclude_unset=True) == {"tone": "G"}

    def test_content_is_stored_as_typed(self) -> None:
        changes = ChordChartChangesInput.model_validate({"content": "  [G]Santo\n"})
        assert changes.content == "  [G]Santo\n"


class TestRefusedChanges:
    @pytest.mark.parametrize(
        "payload",
        [
            {},
            {"content": "  "},
            {"tone": " "},
            {"tone": "ABCD"},
            {"instrument": ""},
            {"instrument": "x" * 51},
            {"instrument": None},
            {"song_id": 2},
        ],
    )
    def test_invalid_body(self, payload: dict[str, object]) -> None:
        with pytest.raises(ValidationError):
            ChordChartChangesInput.model_validate(payload)
