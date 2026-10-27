from collections.abc import Iterator
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from dependency_injector import providers

from features.bible.models import BibleVideo, BibleVideoPlace
from features.bible.tests.fakes import FakeYouTubeMetadataClient, FixedClock

if TYPE_CHECKING:
    from config.di import Container

VIDEOS_URL = "/api/bible/videos/"
ORDER_URL = "/api/bible/videos/order/"
PROGRESS_URL = "/api/bible/progress/"
SYNC_URL = "/api/bible/progress/sync/"
NOW = datetime(2026, 10, 27, 13, 0, tzinfo=UTC)


def video_url(video_id: int) -> str:
    return f"{VIDEOS_URL}{video_id}/"


def places_url(video_id: int) -> str:
    return f"{VIDEOS_URL}{video_id}/places/"


def seed_video(youtube_id: str, *places: tuple[str, int | None, int]) -> BibleVideo:
    """A video row with ``(book, chapter, position)`` places, bypassing the service."""
    video = BibleVideo.objects.create(
        kind="video",
        youtube_id=youtube_id,
        url=f"https://www.youtube.com/watch?v={youtube_id}",
        title=f"Vídeo {youtube_id}",
        thumbnail_url=f"https://i.ytimg.com/vi/{youtube_id}/hqdefault.jpg",
    )
    for book, chapter, position in places:
        BibleVideoPlace.objects.create(video=video, book=book, chapter=chapter, position=position)
    return video


@pytest.fixture
def youtube(di_container: "Container") -> Iterator[FakeYouTubeMetadataClient]:
    """Every API test talks to a fake YouTube; none reaches the network."""
    fake = FakeYouTubeMetadataClient()
    with di_container.youtube_metadata_client.override(providers.Object(fake)):
        yield fake


@pytest.fixture
def clock(di_container: "Container") -> Iterator[FixedClock]:
    fixed = FixedClock(NOW)
    with di_container.clock.override(providers.Object(fixed)):
        yield fixed
