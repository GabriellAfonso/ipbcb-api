"""DTOs and request parsing for the Sunday setlist (specs/017-sunday-setlist-push).

Parsing checks shape only — types, ranges, lengths. The rules that need the whole setlist
(Sunday, unique positions) live in ``services/setlist_rules.py``.
"""

from datetime import date, datetime
from typing import Any, Literal

from core.application.dtos.push_dtos import PushOutcome
from core.application.dtos.strict_base import StrictBaseModel
from core.domain.exceptions import ValidationError
from core.http.parsing import require_int, require_object_body
from features.songs.models.setlist import MAX_POSITION, MIN_POSITION

TONE_MAX_LENGTH = 3


class SetlistItemInput(StrictBaseModel):
    """One item as sent by the app, already shape-checked."""

    song_id: int
    position: int
    tone: str


class SetlistItemDTO(StrictBaseModel):
    position: int
    song_id: int
    title: str
    artist: str
    tone: str


class SetlistDTO(StrictBaseModel):
    """A stored setlist as answered to the app; ``items`` ordered by position."""

    date: date
    items: list[SetlistItemDTO]
    saved_by_name: str | None
    saved_at: datetime


ReminderOutcome = Literal["outside_window", "no_setlist", "confirmed", "already_sent", "sent"]


class ReminderRunReport(StrictBaseModel):
    """What one ``send_setlist_reminders`` run did."""

    outcome: ReminderOutcome
    setlist_date: date | None = None
    slot: datetime | None = None
    push: PushOutcome | None = None


def parse_setlist_date(raw: str) -> date:
    """The ``{date}`` path segment as a date.

    >>> parse_setlist_date("2026-10-04")
    datetime.date(2026, 10, 4)
    """
    # The length check rejects "20261004", which ``fromisoformat`` accepts since Python 3.11.
    error = ValidationError(f"Setlist date must be YYYY-MM-DD, got {raw!r}.")
    if len(raw) != len("YYYY-MM-DD"):
        raise error
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise error from None


def parse_setlist_items(body: Any) -> list[SetlistItemInput]:
    """The ``items`` of a save request, each shape-checked.

    >>> parse_setlist_items({"items": [{"song_id": 12, "position": 1, "tone": "G"}]})
    [SetlistItemInput(song_id=12, position=1, tone='G')]
    """
    items = require_object_body(body).get("items")
    if not isinstance(items, list) or not items:
        raise ValidationError(
            f"Field 'items' must be a non-empty list of objects, got {type(items).__name__}."
        )
    return [_parse_item(index, raw) for index, raw in enumerate(items)]


def _parse_item(index: int, raw: Any) -> SetlistItemInput:
    if not isinstance(raw, dict):
        raise ValidationError(f"items[{index}] must be an object, got {type(raw).__name__}.")
    position = require_int(raw.get("position"), f"items[{index}].position")
    if not MIN_POSITION <= position <= MAX_POSITION:
        raise ValidationError(
            f"items[{index}].position must be between {MIN_POSITION} and {MAX_POSITION}, "
            f"got {position}."
        )
    song_id = require_int(raw.get("song_id"), f"items[{index}].song_id")
    return SetlistItemInput(song_id=song_id, position=position, tone=_parse_tone(index, raw))


def _parse_tone(index: int, raw: dict[str, Any]) -> str:
    tone = raw.get("tone")
    if not isinstance(tone, str) or not 1 <= len(tone.strip()) <= TONE_MAX_LENGTH:
        raise ValidationError(
            f"items[{index}].tone must be a string of 1 to {TONE_MAX_LENGTH} characters, "
            f"got {tone!r}."
        )
    return tone.strip()
