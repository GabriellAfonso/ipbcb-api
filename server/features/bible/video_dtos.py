"""DTOs of Bible videos and their places (specs/025-bible-videos data-model)."""

from pydantic import Field

from core.application.dtos.strict_base import StrictBaseModel
from features.bible.domain.youtube_links import YouTubeKind

# Every chapter (1,189) and every whole book (66) once: the most places one video can have.
MAX_PLACES_PER_VIDEO = 1255
MAX_VIDEOS_PER_ORDER = 1000


class BiblePlaceDTO(StrictBaseModel):
    """A place as the app sends it; ``book`` is not canonical yet.

    >>> BiblePlaceDTO(book="gn", chapter=None)
    """

    book: str = Field(min_length=1, max_length=8)
    chapter: int | None = Field(ge=1)


class BibleVideoPlaceDTO(StrictBaseModel):
    book: str
    chapter: int | None
    position: int


class BibleVideoDTO(StrictBaseModel):
    """A video with its places, as listed (contracts/api.md)."""

    id: int
    kind: YouTubeKind
    youtube_id: str
    url: str
    title: str
    thumbnail_url: str
    places: list[BibleVideoPlaceDTO]


class YouTubeMetadataDTO(StrictBaseModel):
    title: str
    thumbnail_url: str


class BibleVideoNewDTO(StrictBaseModel):
    """Everything stored about a video before its places."""

    kind: YouTubeKind
    youtube_id: str
    url: str
    title: str
    thumbnail_url: str


class BibleVideoCreateDTO(StrictBaseModel):
    """``POST api/bible/videos/``. An empty ``places`` is refused by the service with
    ``BIBLE_PLACE_INVALID``, not here, so the app gets the place error code."""

    url: str = Field(min_length=1, max_length=2000)
    places: list[BiblePlaceDTO] = Field(max_length=MAX_PLACES_PER_VIDEO)


class BibleVideoPlacesDTO(StrictBaseModel):
    """``PUT api/bible/videos/{id}/places/``: the whole desired set."""

    places: list[BiblePlaceDTO] = Field(max_length=MAX_PLACES_PER_VIDEO)


class BibleVideoOrderDTO(StrictBaseModel):
    """``PUT api/bible/videos/order/``: the videos of one place, first to last."""

    book: str = Field(min_length=1, max_length=8)
    chapter: int | None = Field(ge=1)
    video_ids: list[int] = Field(max_length=MAX_VIDEOS_PER_ORDER)


class BiblePlaceQueryDTO(StrictBaseModel):
    """``DELETE api/bible/videos/{id}/places/?book=Gn&chapter=1``; no ``chapter`` = whole book."""

    book: str = Field(min_length=1, max_length=8)
    chapter: int | None = Field(default=None, ge=1)
