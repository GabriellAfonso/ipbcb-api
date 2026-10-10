from datetime import date, datetime
from typing import Annotated, Any, Self

from pydantic import (
    AfterValidator,
    Field,
    HttpUrl,
    StringConstraints,
    TypeAdapter,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic import ValidationError as PydanticValidationError

from core.application.dtos.strict_base import StrictBaseModel
from core.domain.exceptions import ValidationError

_HTTP_URL = TypeAdapter(HttpUrl)


def _require_http_url(v: str) -> str:
    # Validated but stored as typed: HttpUrl would normalize it (trailing slash, punycode).
    if not v:
        return v
    try:
        _HTTP_URL.validate_python(v)
    except PydanticValidationError:
        raise ValueError(f"youtube_link must be an http(s) URL; got {v!r}") from None
    return v


# Field rules shared by create and edit, so the two can never drift (spec 018 FR-002).
_SongText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
_YoutubeLink = Annotated[
    str,
    StringConstraints(strip_whitespace=True),
    Field(max_length=200),
    AfterValidator(_require_http_url),
]


class NewSongInput(StrictBaseModel):
    """A song to add to the catalogue. Lengths mirror the ``Song`` columns.

    >>> NewSongInput(title=" Oceans ", artist="Hillsong")
    NewSongInput(title='Oceans', artist='Hillsong', youtube_link='')
    """

    title: _SongText
    artist: _SongText
    youtube_link: _YoutubeLink = ""


class SongChangesInput(StrictBaseModel):
    """A partial edit of a catalogue song: only the fields sent change.

    ``None`` means "not sent" and is never written; an explicit ``null`` is refused, since
    only the link can be cleared, and with ``""``.

    >>> SongChangesInput(title=" Oceans ").model_dump(exclude_unset=True)
    {'title': 'Oceans'}
    """

    title: _SongText | None = None
    artist: _SongText | None = None
    youtube_link: _YoutubeLink | None = None

    @field_validator("title", "artist", "youtube_link", mode="before")
    @classmethod
    def reject_null(cls, v: object, info: ValidationInfo) -> object:
        # Runs only for keys the client sent: pydantic does not validate defaults.
        if v is None:
            raise ValueError(f"{info.field_name} must not be null; omit the field to keep it")
        return v

    @model_validator(mode="after")
    def require_a_change(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("send at least one of: title, artist, youtube_link; got {}")
        return self


class SongUsage(StrictBaseModel):
    """What in the Sunday record still points at a song, blocking its deletion.

    >>> SongUsage(plays=2, setlist_dates=[date(2026, 10, 18)]).in_use
    True
    """

    # Distinct dates, not Played rows: the message says "N domingos" (spec 018 FR-014).
    plays: int
    setlist_dates: list[date]

    @property
    def in_use(self) -> bool:
        return self.plays > 0 or bool(self.setlist_dates)


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
