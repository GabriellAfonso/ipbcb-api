"""YouTube oEmbed over ``requests`` (specs/025-bible-videos R-04). The only place in the Bible
feature that talks HTTP; no API key is needed."""

import logging
from collections.abc import Mapping
from typing import Protocol

import requests

from core.domain.exceptions import BibleVideoLookupFailedError, BibleVideoUnavailableError
from features.bible.domain.youtube_links import YouTubeKind, YouTubeTarget, video_thumbnail_url
from features.bible.models.bible_video import THUMBNAIL_URL_MAX_LENGTH, TITLE_MAX_LENGTH
from features.bible.video_dtos import YouTubeMetadataDTO

logger = logging.getLogger(__name__)

_OEMBED_URL = "https://www.youtube.com/oembed"
# The leader waits on this call while saving, so a slow YouTube must not hold them long.
_TIMEOUT_SECONDS = 5
# YouTube answers 401/403 for private or non-embeddable targets, 404 for removed ones and 400
# for a malformed or nonexistent playlist id.
_UNAVAILABLE_STATUSES = frozenset({400, 401, 403, 404})


class HttpResponseLike(Protocol):
    @property
    def status_code(self) -> int: ...

    def json(self) -> object: ...


class HttpSessionLike(Protocol):
    def get(self, url: str, *, params: Mapping[str, str], timeout: float) -> HttpResponseLike: ...


class HttpYouTubeOEmbedClient:
    """``YouTubeMetadataClient`` over oEmbed.

    >>> HttpYouTubeOEmbedClient().fetch(parse_youtube_link("youtu.be/dQw4w9WgXcQ"))
    YouTubeMetadataDTO(title='...', thumbnail_url='https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg')
    """

    def __init__(self, session: HttpSessionLike | None = None) -> None:
        self._session: HttpSessionLike = session or requests.Session()

    def fetch(self, target: YouTubeTarget) -> YouTubeMetadataDTO:
        response = self._get(target)
        if response.status_code in _UNAVAILABLE_STATUSES:
            raise BibleVideoUnavailableError(target.youtube_id, response.status_code)
        if response.status_code != 200:
            raise _lookup_failed(target, f"status {response.status_code}")
        return _metadata(target, response)

    def _get(self, target: YouTubeTarget) -> HttpResponseLike:
        params = {"url": target.url, "format": "json"}
        try:
            return self._session.get(_OEMBED_URL, params=params, timeout=_TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            raise _lookup_failed(target, type(exc).__name__) from exc


def _metadata(target: YouTubeTarget, response: HttpResponseLike) -> YouTubeMetadataDTO:
    try:
        body = response.json()
    except ValueError as exc:
        raise _lookup_failed(target, "body is not JSON") from exc
    fields = body if isinstance(body, dict) else {}
    title = fields.get("title")
    thumbnail = (
        video_thumbnail_url(target.youtube_id)
        if target.kind is YouTubeKind.VIDEO
        else fields.get("thumbnail_url")
    )
    if not isinstance(title, str) or not title.strip() or not isinstance(thumbnail, str):
        raise _lookup_failed(target, "title or thumbnail_url missing")
    return YouTubeMetadataDTO(
        title=title.strip()[:TITLE_MAX_LENGTH],
        thumbnail_url=thumbnail[:THUMBNAIL_URL_MAX_LENGTH],
    )


def _lookup_failed(target: YouTubeTarget, reason: str) -> BibleVideoLookupFailedError:
    logger.warning(
        "bible_video_lookup_failed", extra={"youtube_id": target.youtube_id, "reason": reason}
    )
    return BibleVideoLookupFailedError(reason)
