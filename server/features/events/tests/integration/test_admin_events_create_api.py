"""US3 — the panel creates an event (specs/020-church-events)."""

from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from rest_framework.test import APIClient

from conftest import make_member_client, make_role_client
from core.domain.access import Role
from features.events.models.event import Event
from features.events.tests.images import fake_image_upload, image_upload
from features.events.tests.integration.conftest import ADMIN_URL, PUBLIC_URL, TODAY

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("clock")]


def _media_client() -> APIClient:
    client, _ = make_role_client(Role.MEDIA, username="midia")
    return client


def _post(client: APIClient, **fields: Any) -> Any:
    body: dict[str, Any] = {"title": "Retiro", "start_date": TODAY.isoformat(), **fields}
    if "image" not in fields:
        body["image"] = image_upload()
    body = {key: value for key, value in body.items() if value is not ...}
    return client.post(ADMIN_URL, body, format="multipart")


def _stored_size(media_root: Path, image_url: str) -> tuple[int, int]:
    relative = image_url.split("/ipbcb/media/", 1)[1]
    with Image.open(BytesIO((media_root / relative).read_bytes())) as stored:
        assert stored.format == "JPEG"
        return stored.size


def test_minimal_create_is_public_with_nulls_and_creator(media_root: Path) -> None:
    client, user = make_role_client(Role.MEDIA, username="midia")

    response = _post(client)

    assert response.status_code == 201
    body = response.data
    assert body["visibility"] == "public"
    assert [body[k] for k in ("end_date", "start_time", "location", "description")] == [None] * 4
    assert body["created_by"]["id"] == str(user.pk)
    assert APIClient().get(PUBLIC_URL).data[0]["id"] == body["id"]


@pytest.mark.parametrize(
    ("size", "image_format", "stored"),
    [((4000, 2250), "PNG", (1920, 1080)), ((1280, 720), "JPEG", (1280, 720))],
)
def test_image_is_stored_as_jpeg_within_1920_by_1080(
    media_root: Path, size: tuple[int, int], image_format: str, stored: tuple[int, int]
) -> None:
    response = _post(_media_client(), image=image_upload(size, image_format, "p.png"))

    assert response.status_code == 201
    assert _stored_size(media_root, response.data["image_url"]) == stored


def test_ratio_within_tolerance_is_accepted(media_root: Path) -> None:
    assert _post(_media_client(), image=image_upload((1000, 563))).status_code == 201


@pytest.mark.parametrize(
    ("upload_args", "message_part"),
    [
        (((1600, 1000),), "1600x1000"),
        (((620, 349),), "640x360"),
        (((1280, 720), "GIF", "p.gif"), "GIF"),
    ],
)
def test_bad_image_is_a_field_error(
    media_root: Path, upload_args: tuple[Any, ...], message_part: str
) -> None:
    response = _post(_media_client(), image=image_upload(*upload_args))

    assert response.status_code == 400
    assert message_part in response.data["field_errors"]["image"][0]
    assert not Event.objects.exists()
    assert not (media_root / "events").exists() or not any((media_root / "events").iterdir())


def test_not_an_image_is_a_field_error(media_root: Path) -> None:
    response = _post(_media_client(), image=fake_image_upload())

    assert response.status_code == 400
    assert "image" in response.data["field_errors"]


@pytest.mark.parametrize(
    ("fields", "field"),
    [
        ({"title": "   "}, "title"),
        ({"start_date": ...}, "start_date"),
        ({"image": ...}, "image"),
        ({"end_date": "2026-11-13"}, "end_date"),
        ({"visibility": "secret"}, "visibility"),
        ({"start_time": "7pm"}, "start_time"),
    ],
)
def test_invalid_field_is_a_field_error(
    media_root: Path, fields: dict[str, Any], field: str
) -> None:
    response = _post(_media_client(), **fields)

    assert response.status_code == 400
    assert response.data["error_code"] == "VALIDATION_ERROR"
    assert field in response.data["field_errors"]
    assert not Event.objects.exists()


def test_blank_optional_text_is_stored_as_null(media_root: Path) -> None:
    response = _post(_media_client(), location="   ", description="", end_date="")

    assert response.status_code == 201
    assert (response.data["location"], response.data["description"]) == (None, None)
    assert response.data["end_date"] is None


def test_full_create(media_root: Path) -> None:
    response = _post(
        _media_client(),
        end_date="2026-11-16",
        start_time="19:30",
        location="Templo",
        description="Três dias",
        visibility="members",
    )

    assert response.status_code == 201
    assert (response.data["end_date"], response.data["start_time"]) == ("2026-11-16", "19:30")
    assert response.data["visibility"] == "members"


@pytest.mark.parametrize("role", [Role.ADMIN, Role.LEADER, Role.MEDIA])
def test_every_panel_role_creates(media_root: Path, role: Role) -> None:
    client, _ = make_role_client(role)

    assert _post(client).status_code == 201


def test_member_without_role_is_refused(media_root: Path) -> None:
    client, _ = make_member_client()

    response = _post(client)

    assert response.status_code == 403
    assert response.data["error_code"] == "PERMISSION_DENIED"


def test_anonymous_is_401(media_root: Path) -> None:
    assert _post(APIClient()).status_code == 401
