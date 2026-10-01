from datetime import date
from typing import Any

import pytest

from core.domain.exceptions import ValidationError
from features.songs.setlist_dtos import SetlistItemInput, parse_setlist_date, parse_setlist_items


class TestParseSetlistDate:
    def test_iso_date(self) -> None:
        assert parse_setlist_date("2026-10-04") == date(2026, 10, 4)

    @pytest.mark.parametrize("raw", ["2026-13-01", "04/10/2026", "", "20261004", "2026-10-4"])
    def test_bad_formats_name_the_value(self, raw: str) -> None:
        with pytest.raises(ValidationError, match="YYYY-MM-DD"):
            parse_setlist_date(raw)


def _item(**overrides: Any) -> dict[str, Any]:
    return {"song_id": 12, "position": 1, "tone": "G", **overrides}


class TestParseSetlistItems:
    def test_valid_items_and_trimmed_tone(self) -> None:
        body = {"items": [_item(), _item(song_id=5, position=2, tone=" A# ")]}
        assert parse_setlist_items(body) == [
            SetlistItemInput(song_id=12, position=1, tone="G"),
            SetlistItemInput(song_id=5, position=2, tone="A#"),
        ]

    @pytest.mark.parametrize(
        "body",
        [[], "x", {}, {"items": []}, {"items": "x"}, {"items": [1]}, {"items": None}],
    )
    def test_bad_shapes(self, body: Any) -> None:
        with pytest.raises(ValidationError):
            parse_setlist_items(body)

    @pytest.mark.parametrize(
        "item",
        [
            _item(song_id="x"),
            _item(song_id=None),
            _item(position="first"),
            _item(position=0),
            _item(position=11),
            _item(tone=""),
            _item(tone="   "),
            _item(tone="Bbm7"),
            _item(tone=3),
            {"song_id": 1, "position": 1},
        ],
    )
    def test_bad_items_name_the_field(self, item: dict[str, Any]) -> None:
        with pytest.raises(ValidationError, match=r"items\[0\]"):
            parse_setlist_items({"items": [item]})
