from datetime import date, datetime
from typing import Annotated, Any

from pydantic import Field, HttpUrl, StringConstraints, TypeAdapter, field_validator
from pydantic import ValidationError as PydanticValidationError

from core.application.dtos.strict_base import StrictBaseModel
from core.domain.exceptions import ValidationError

_SongText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
_HTTP_URL = TypeAdapter(HttpUrl)


class NewSongInput(StrictBaseModel):
    """A song to add to the catalogue. Lengths mirror the ``Song`` columns.

    >>> NewSongInput(title=" Oceans ", artist="Hillsong")
    NewSongInput(title='Oceans', artist='Hillsong', youtube_link='')
    """

    title: _SongText
    artist: _SongText
    youtube_link: Annotated[
        str, StringConstraints(strip_whitespace=True), Field(max_length=200)
    ] = ""

    @field_validator("youtube_link")
    @classmethod
    def youtube_link_is_url(cls, v: str) -> str:
        # Validated but stored as typed: HttpUrl would normalize it (trailing slash, punycode).
        if not v:
            return v
        try:
            _HTTP_URL.validate_python(v)
        except PydanticValidationError:
            raise ValueError(f"youtube_link must be an http(s) URL; got {v!r}") from None
        return v


class SundaySongDTO(StrictBaseModel):
    """Single song entry within a Sunday set."""

    song_id: int
    position: int
    song: str
    artist: str
    tone: str


class SundaySetDTO(StrictBaseModel):
    """A Sunday service with its songs."""

    date: str
    songs: list[SundaySongDTO]


class PlayInput(StrictBaseModel):
    """Single play entry for registering Sunday plays."""

    song_id: int
    position: int
    tone: str = ""

    @field_validator("position")
    @classmethod
    def position_in_range(cls, v: int) -> int:
        if v < 1 or v > 10:
            raise ValueError("position must be between 1 and 10")
        return v


def parse_register_plays_input(payload: dict[str, Any]) -> tuple[date, list[PlayInput]]:
    """Parse and validate the register plays payload.

    Raises ``ValidationError`` on invalid input.

    >>> parse_register_plays_input({"date": "2026-03-15", "plays": [{"song_id": 1, "position": 1}]})
    (datetime.date(2026, 3, 15), [PlayInput(song_id=1, position=1, tone='')])
    """
    date_str = (payload.get("date") or "").strip()
    plays_raw = payload.get("plays")

    if not date_str:
        raise ValidationError("Missing field: date.")
    if not isinstance(plays_raw, list) or not plays_raw:
        raise ValidationError("Missing/invalid field: plays (must be a non-empty list).")

    try:
        date_value = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise ValidationError("Invalid date format. Use YYYY-MM-DD.")

    play_inputs: list[PlayInput] = []
    for idx, item in enumerate(plays_raw):
        if not isinstance(item, dict):
            raise ValidationError(f"plays[{idx}] must be an object.")

        song_id = item.get("song_id")
        position = item.get("position")
        tone = (item.get("tone") or "").strip()

        if song_id is None or position is None:
            raise ValidationError(f"plays[{idx}] song_id/position must be integers.")

        try:
            song_id_int = int(song_id)
            position_int = int(position)
        except (TypeError, ValueError):
            raise ValidationError(f"plays[{idx}] song_id/position must be integers.")

        if position_int < 1 or position_int > 10:
            raise ValidationError(f"plays[{idx}] position must be between 1 and 10.")

        play_inputs.append(PlayInput(song_id=song_id_int, position=position_int, tone=tone))

    return date_value, play_inputs
