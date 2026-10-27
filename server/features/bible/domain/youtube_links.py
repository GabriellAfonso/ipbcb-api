"""Reading a pasted YouTube link into what it points to (specs/025-bible-videos R-03).

Pure, so every accepted shape is tested without network. The canonical URL built here is what
makes the duplicate check independent of how the link was pasted.
"""

import re
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import parse_qs, urlsplit

_VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")
_PLAYLIST_ID = re.compile(r"[A-Za-z0-9_-]{10,64}")
_START_TIME = re.compile(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s?)?")
_YOUTUBE_HOSTS = frozenset({"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"})
_SHORT_HOST = "youtu.be"
_VIDEO_PATH_PREFIXES = ("/shorts/", "/live/")

Query = dict[str, list[str]]


class YouTubeKind(StrEnum):
    VIDEO = "video"
    PLAYLIST = "playlist"


@dataclass(frozen=True)
class YouTubeTarget:
    """A video or playlist id, plus the start time a video link carried.

    >>> YouTubeTarget(YouTubeKind.VIDEO, "dQw4w9WgXcQ", 90).url
    'https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=90'
    """

    kind: YouTubeKind
    youtube_id: str
    start_seconds: int | None = None

    @property
    def url(self) -> str:
        if self.kind is YouTubeKind.PLAYLIST:
            return f"https://www.youtube.com/playlist?list={self.youtube_id}"
        start = f"&t={self.start_seconds}" if self.start_seconds else ""
        return f"https://www.youtube.com/watch?v={self.youtube_id}{start}"


def video_thumbnail_url(youtube_id: str) -> str:
    """Thumbnail served for every public video, without asking YouTube.

    >>> video_thumbnail_url("dQw4w9WgXcQ")
    'https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg'
    """
    return f"https://i.ytimg.com/vi/{youtube_id}/hqdefault.jpg"


def parse_youtube_link(link: str) -> YouTubeTarget | None:
    """What ``link`` points to, or None when it is not a supported YouTube link.
    ``watch?v=X&list=Y`` is the video X: the user linked that video.

    >>> parse_youtube_link("youtu.be/dQw4w9WgXcQ?t=1m30s")
    YouTubeTarget(kind=<YouTubeKind.VIDEO: 'video'>, youtube_id='dQw4w9WgXcQ', start_seconds=90)
    """
    parts = _split(link.strip())
    if parts is None:
        return None
    host, path, query = parts
    if host == _SHORT_HOST:
        return _video(path.strip("/"), query)
    if host not in _YOUTUBE_HOSTS:
        return None
    return _from_youtube_path(path.rstrip("/"), query)


def _split(link: str) -> tuple[str, str, Query] | None:
    if "://" not in link:
        link = f"https://{link}"
    parsed = urlsplit(link)
    if parsed.scheme not in ("http", "https"):
        return None
    return (parsed.hostname or "").lower(), parsed.path, parse_qs(parsed.query)


def _from_youtube_path(path: str, query: Query) -> YouTubeTarget | None:
    if path == "/watch":
        return _video(_first(query, "v"), query)
    if path == "/playlist":
        return _playlist(_first(query, "list"))
    for prefix in _VIDEO_PATH_PREFIXES:
        if path.startswith(prefix):
            return _video(path.removeprefix(prefix), query)
    return None


def _video(youtube_id: str, query: Query) -> YouTubeTarget | None:
    if not _VIDEO_ID.fullmatch(youtube_id):
        return None
    start = _start_seconds(_first(query, "t") or _first(query, "start"))
    return YouTubeTarget(YouTubeKind.VIDEO, youtube_id, start)


def _playlist(youtube_id: str) -> YouTubeTarget | None:
    if not _PLAYLIST_ID.fullmatch(youtube_id):
        return None
    return YouTubeTarget(YouTubeKind.PLAYLIST, youtube_id)


def _start_seconds(raw: str) -> int | None:
    """``90``, ``90s``, ``1m30s``, ``1h2m3s`` in seconds; None when absent, zero or unreadable —
    a bad start time drops the start, it does not make the link invalid."""
    match = _START_TIME.fullmatch(raw)
    if not raw or match is None:
        return None
    hours, minutes, seconds = (int(group or 0) for group in match.groups())
    return hours * 3600 + minutes * 60 + seconds or None


def _first(query: Query, key: str) -> str:
    values = query.get(key)
    return values[0] if values else ""
