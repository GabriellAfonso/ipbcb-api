"""Event images through the media check (specs/020-church-events FR-019 to FR-021).

The access table of contracts/events-api.md, and that every other folder still answers 401 to
an anonymous caller.
"""

from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from conftest import make_auth_client, make_member_client, make_user
from features.events.domain.event_enums import EventVisibility
from features.events.models.event import Event
from features.media.tests.integration.conftest import GALLERY_FILE, media_url

WriteMedia = Callable[..., Path]
PUBLIC_IMAGE = "events/0a1b2c.jpg"
MEMBERS_IMAGE = "events/9f8e7d.jpg"
ORPHAN_IMAGE = "events/orphan.jpg"


@pytest.fixture
def event_images(write_media: WriteMedia) -> None:
    for path in (PUBLIC_IMAGE, MEMBERS_IMAGE, ORPHAN_IMAGE):
        write_media(path)
    _event(PUBLIC_IMAGE, EventVisibility.PUBLIC)
    _event(MEMBERS_IMAGE, EventVisibility.MEMBERS)


def _event(image_path: str, visibility: EventVisibility) -> Event:
    return Event.objects.create(
        title="Evento",
        start_date=date(2026, 11, 14),
        image_path=image_path,
        visibility=visibility.value,
    )


def _non_member() -> APIClient:
    return make_auth_client(make_user(username="visitor"))


def _member() -> APIClient:
    client, _ = make_member_client()
    return client


def _status(client: APIClient, path: str) -> int:
    return int(client.get(media_url(path)).status_code)


@pytest.mark.django_db
@pytest.mark.usefixtures("event_images")
class TestEventImageAccess:
    @pytest.mark.parametrize("make_client", [APIClient, _non_member, _member])
    def test_public_event_image_is_served_to_anyone(
        self, make_client: Callable[[], APIClient]
    ) -> None:
        response = make_client().get(media_url(PUBLIC_IMAGE))

        assert response.status_code == 200
        assert response["X-Accel-Redirect"] == f"/ipbcb/protected-media/{PUBLIC_IMAGE}"
        assert response["Cache-Control"] == "private, no-cache"
        assert response["Content-Type"] == "image/jpeg"

    def test_members_event_image_is_served_to_members(self) -> None:
        assert _status(_member(), MEMBERS_IMAGE) == 200

    @pytest.mark.parametrize("make_client", [APIClient, _non_member])
    def test_members_event_image_is_404_to_others(
        self, make_client: Callable[[], APIClient]
    ) -> None:
        response = make_client().get(media_url(MEMBERS_IMAGE))

        assert response.status_code == 404
        assert "X-Accel-Redirect" not in response

    @pytest.mark.parametrize("make_client", [APIClient, _member])
    def test_file_of_no_event_is_404(self, make_client: Callable[[], APIClient]) -> None:
        assert _status(make_client(), ORPHAN_IMAGE) == 404

    @pytest.mark.parametrize("path", [PUBLIC_IMAGE, MEMBERS_IMAGE])
    def test_invalid_or_expired_token_is_401(self, path: str) -> None:
        malformed = APIClient()
        malformed.credentials(HTTP_AUTHORIZATION="Bearer not-a-jwt")
        token = AccessToken.for_user(make_user(username="expired"))
        token.set_exp(lifetime=-timedelta(minutes=1))
        expired = APIClient()
        expired.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        assert _status(malformed, path) == 401
        assert _status(expired, path) == 401

    def test_visibility_change_takes_effect_on_the_next_request(self) -> None:
        Event.objects.filter(image_path=PUBLIC_IMAGE).update(
            visibility=EventVisibility.MEMBERS.value
        )

        assert _status(APIClient(), PUBLIC_IMAGE) == 404


@pytest.mark.django_db
class TestAnonymousStillLockedOutElsewhere:
    @pytest.mark.parametrize(
        "path", [GALLERY_FILE, "profiles/ana/x.png", "members/x.jpg", "events-old/x.jpg"]
    )
    def test_other_folders_are_401(self, write_media: WriteMedia, path: str) -> None:
        write_media(path)

        assert _status(APIClient(), path) == 401

    @pytest.mark.parametrize(
        "path", ["events/../members/x.jpg", "events/%2e%2e/members/x.jpg", "events/"]
    )
    def test_path_tricks_under_events_are_rejected(
        self, write_media: WriteMedia, path: str
    ) -> None:
        write_media("members/x.jpg")

        response = APIClient().get(media_url(path))

        assert response.status_code == 404
        assert "X-Accel-Redirect" not in response
