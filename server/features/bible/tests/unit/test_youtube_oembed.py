"""HttpYouTubeOEmbedClient against a named fake HTTP session (no network)."""

from collections.abc import Mapping

import pytest
import requests

from core.domain.exceptions import BibleVideoLookupFailedError, BibleVideoUnavailableError
from features.bible.domain.youtube_links import YouTubeKind, YouTubeTarget
from features.bible.repositories.youtube_oembed import HttpYouTubeOEmbedClient

VIDEO = YouTubeTarget(YouTubeKind.VIDEO, "dQw4w9WgXcQ", 90)
PLAYLIST = YouTubeTarget(YouTubeKind.PLAYLIST, "PLx0sYbCqOb8TBPRdmBHs5Iftvv9TPboYG")


class FakeOEmbedResponse:
    def __init__(self, status_code: int, body: object = None, invalid_json: bool = False) -> None:
        self.status_code = status_code
        self._body = body
        self._invalid_json = invalid_json

    def json(self) -> object:
        if self._invalid_json:
            raise ValueError("Expecting value")
        return self._body


class FakeOEmbedSession:
    """Returns ``response`` or raises ``error``; records each call."""

    def __init__(
        self, response: FakeOEmbedResponse | None = None, error: Exception | None = None
    ) -> None:
        self.response = response
        self.error = error
        self.calls: list[tuple[str, Mapping[str, str], float]] = []

    def get(self, url: str, *, params: Mapping[str, str], timeout: float) -> FakeOEmbedResponse:
        self.calls.append((url, params, timeout))
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response


def _client(session: FakeOEmbedSession) -> HttpYouTubeOEmbedClient:
    return HttpYouTubeOEmbedClient(session)


def test_video_takes_title_from_oembed_and_the_fixed_thumbnail() -> None:
    session = FakeOEmbedSession(
        FakeOEmbedResponse(200, {"title": "  Gênesis 1  ", "thumbnail_url": "https://x/y.jpg"})
    )

    metadata = _client(session).fetch(VIDEO)

    assert metadata.title == "Gênesis 1"
    assert metadata.thumbnail_url == "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg"
    url, params, timeout = session.calls[0]
    assert url == "https://www.youtube.com/oembed"
    assert params == {"url": VIDEO.url, "format": "json"}
    assert timeout == 5


def test_playlist_takes_the_oembed_thumbnail() -> None:
    body = {"title": "Série Romanos", "thumbnail_url": "https://i.ytimg.com/vi/abc/hq.jpg"}
    metadata = _client(FakeOEmbedSession(FakeOEmbedResponse(200, body))).fetch(PLAYLIST)
    assert metadata.thumbnail_url == "https://i.ytimg.com/vi/abc/hq.jpg"


def test_long_title_is_cut_to_the_column() -> None:
    body = {"title": "x" * 400, "thumbnail_url": "https://x/y.jpg"}
    metadata = _client(FakeOEmbedSession(FakeOEmbedResponse(200, body))).fetch(VIDEO)
    assert len(metadata.title) == 300


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_refused_target_is_unavailable(status: int) -> None:
    with pytest.raises(BibleVideoUnavailableError) as caught:
        _client(FakeOEmbedSession(FakeOEmbedResponse(status))).fetch(VIDEO)
    assert caught.value.status == status


@pytest.mark.parametrize(
    "session",
    [
        FakeOEmbedSession(FakeOEmbedResponse(500)),
        FakeOEmbedSession(FakeOEmbedResponse(429)),
        FakeOEmbedSession(error=requests.Timeout("read timed out")),
        FakeOEmbedSession(error=requests.ConnectionError("dns")),
        FakeOEmbedSession(FakeOEmbedResponse(200, invalid_json=True)),
        FakeOEmbedSession(FakeOEmbedResponse(200, ["not", "an", "object"])),
        FakeOEmbedSession(FakeOEmbedResponse(200, {"title": ""})),
        FakeOEmbedSession(FakeOEmbedResponse(200, {"title": "Série"})),
    ],
)
def test_anything_else_is_a_lookup_failure(session: FakeOEmbedSession) -> None:
    target = PLAYLIST if session.response and session.response.status_code == 200 else VIDEO
    with pytest.raises(BibleVideoLookupFailedError):
        _client(session).fetch(target)
