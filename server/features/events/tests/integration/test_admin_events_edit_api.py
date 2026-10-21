"""US4 — the panel edits and deletes events (specs/020-church-events)."""

from datetime import date
from pathlib import Path
from typing import Any

import pytest
from rest_framework.test import APIClient

from conftest import make_role_client
from core.domain.access import Role, Scope
from features.events.domain.event_enums import EventVisibility
from features.events.models.event import Event
from features.events.tests.images import image_upload
from features.events.tests.integration.conftest import (
    PUBLIC_URL,
    MakeEvent,
    admin_detail_url,
    public_detail_url,
)

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("clock")]


def _client(role: Role = Role.MEDIA) -> APIClient:
    client, _ = make_role_client(role, username=f"user_{role.value}")
    return client


def _patch(event_id: int, **fields: Any) -> Any:
    return _client().patch(admin_detail_url(event_id), fields, format="multipart")


def test_patch_changes_only_the_sent_field(make_event: MakeEvent) -> None:
    event = make_event()
    Event.objects.filter(pk=event.pk).update(description="Texto")

    response = _patch(event.pk, location="Templo")

    assert response.status_code == 200
    assert response.data["location"] == "Templo"
    assert response.data["description"] == "Texto"
    assert response.data["image_url"].endswith(event.image_path)


def test_new_image_gets_a_new_url_and_the_old_file_is_removed(
    make_event: MakeEvent, media_root: Path
) -> None:
    event = make_event()

    response = _patch(event.pk, image=image_upload())

    assert response.status_code == 200
    assert not response.data["image_url"].endswith(event.image_path)
    assert not (media_root / event.image_path).exists()


def test_invalid_new_image_changes_nothing(make_event: MakeEvent, media_root: Path) -> None:
    event = make_event()

    response = _patch(event.pk, location="Templo", image=image_upload((1200, 900)))

    assert response.status_code == 400
    assert "image" in response.data["field_errors"]
    event.refresh_from_db()
    assert event.location is None
    assert (media_root / event.image_path).exists()


def test_date_rule_is_checked_on_the_resulting_event(make_event: MakeEvent) -> None:
    event = make_event(start_date=date(2026, 11, 20))

    response = _patch(event.pk, end_date="2026-11-18")

    assert response.status_code == 400
    assert "end_date" in response.data["field_errors"]


def test_clearing_end_date_makes_a_one_day_event(make_event: MakeEvent) -> None:
    event = make_event(end_date=date(2026, 11, 16))

    assert _patch(event.pk, end_date="").data["end_date"] is None


@pytest.mark.parametrize("field", ["title", "start_date"])
def test_required_fields_cannot_be_cleared(make_event: MakeEvent, field: str) -> None:
    response = _patch(make_event().pk, **{field: ""})

    assert response.status_code == 400
    assert field in response.data["field_errors"]


def test_switching_to_members_hides_it_from_non_members(
    make_event: MakeEvent, media_root: Path
) -> None:
    event = make_event()

    _patch(event.pk, visibility="members")

    assert APIClient().get(PUBLIC_URL).data == []
    assert APIClient().get(public_detail_url(event.pk)).status_code == 404
    assert APIClient().get(f"/ipbcb/media/{event.image_path}").status_code == 404


@pytest.mark.parametrize("role", [Role.ADMIN, Role.LEADER, Role.MEDIA])
def test_every_panel_role_deletes_row_and_file(
    make_event: MakeEvent, media_root: Path, role: Role
) -> None:
    event = make_event()
    client = _client(role)

    response = client.delete(admin_detail_url(event.pk))

    assert response.status_code == 204
    assert not Event.objects.filter(pk=event.pk).exists()
    assert not (media_root / event.image_path).exists()
    assert client.get(admin_detail_url(event.pk)).status_code == 404


@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_missing_event_is_404(method: str) -> None:
    response = getattr(_client(), method)(admin_detail_url(999), {}, format="multipart")

    assert response.status_code == 404


def test_role_with_manage_only_cannot_delete(make_event: MakeEvent) -> None:
    # A role whose level was lowered by hand in the Django admin (spec 012 accepted risk).
    from django.contrib.auth.models import Group, Permission

    group = Group.objects.get(name=Role.MEDIA.value)
    group.permissions.remove(Permission.objects.get(codename=f"{Scope.EVENTS.value}__owner"))
    group.permissions.add(Permission.objects.get(codename=f"{Scope.EVENTS.value}__manage"))
    event = make_event()

    response = _client(Role.MEDIA).delete(admin_detail_url(event.pk))

    assert response.status_code == 403
    assert Event.objects.filter(pk=event.pk, visibility=EventVisibility.PUBLIC.value).exists()
