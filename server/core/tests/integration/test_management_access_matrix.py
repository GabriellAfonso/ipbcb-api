"""Every classified management endpoint × every kind of caller (spec 012 SC-004).

``ENDPOINTS`` mirrors spec.md, Endpoint Classification; ``ROLE_LEVELS`` mirrors its scope matrix.
Both are literals on purpose: a change in the code must show up as a failing row here, not
silently move the expectation with it.

The assertion is only about the permission: a caller below the required level gets 403, any
other caller gets anything but 401/403 (400 for the empty body, 404 for the made-up id, 415 for
the photo upload sent as JSON — the permission let them through). Ids point at nothing, so no
fixture is needed and no allowed DELETE destroys shared data.
"""

import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from conftest import make_role_client, make_user
from core.domain.access import Level, Role

MISSING_ID = 999_999

# (method, url, scope, required level)
ENDPOINTS: list[tuple[str, str, str, Level]] = [
    # members
    ("GET", "/api/admin/members/", "members", Level.VIEW),
    ("POST", "/api/admin/members/", "members", Level.MANAGE),
    ("GET", f"/api/admin/members/{MISSING_ID}/", "members", Level.VIEW),
    ("PATCH", f"/api/admin/members/{MISSING_ID}/", "members", Level.MANAGE),
    ("DELETE", f"/api/admin/members/{MISSING_ID}/", "members", Level.OWNER),
    ("GET", "/api/admin/members/options/", "members", Level.VIEW),
    ("PUT", f"/api/admin/members/{MISSING_ID}/photo/", "members", Level.MANAGE),
    ("DELETE", f"/api/admin/members/{MISSING_ID}/photo/", "members", Level.OWNER),
    ("GET", f"/api/admin/members/{MISSING_ID}/history/", "members", Level.VIEW),
    # schedule
    ("POST", "/api/schedule/generate/", "schedule", Level.MANAGE),
    ("POST", "/api/schedule/save/", "schedule", Level.MANAGE),
    # songs
    ("POST", "/api/played/register/", "songs", Level.MANAGE),
    ("POST", "/api/chord-charts/", "songs", Level.MANAGE),
    ("PATCH", f"/api/chord-charts/{MISSING_ID}/", "songs", Level.MANAGE),
    ("POST", "/api/lyrics/", "songs", Level.MANAGE),
    ("PATCH", f"/api/lyrics/{MISSING_ID}/", "songs", Level.MANAGE),
    # reports.hymnal_history
    ("GET", "/api/hymnal-history/occurrences/", "reports.hymnal_history", Level.VIEW),
    ("GET", "/api/hymnal-history/top-hymns/", "reports.hymnal_history", Level.VIEW),
    ("PATCH", "/api/hymnal-history/settings/", "reports.hymnal_history", Level.OWNER),
    ("GET", "/api/hymnal-history/service-windows/", "reports.hymnal_history", Level.VIEW),
    ("POST", "/api/hymnal-history/service-windows/", "reports.hymnal_history", Level.OWNER),
    (
        "GET",
        f"/api/hymnal-history/service-windows/{MISSING_ID}/",
        "reports.hymnal_history",
        Level.VIEW,
    ),
    (
        "PATCH",
        f"/api/hymnal-history/service-windows/{MISSING_ID}/",
        "reports.hymnal_history",
        Level.OWNER,
    ),
    (
        "DELETE",
        f"/api/hymnal-history/service-windows/{MISSING_ID}/",
        "reports.hymnal_history",
        Level.OWNER,
    ),
    # gallery (specs 013 and 014)
    ("POST", "/api/albums/", "gallery", Level.MANAGE),
    ("PATCH", f"/api/albums/{MISSING_ID}/", "gallery", Level.MANAGE),
    ("DELETE", f"/api/albums/{MISSING_ID}/", "gallery", Level.OWNER),
    ("PUT", "/api/albums/order/", "gallery", Level.MANAGE),
    ("PUT", f"/api/albums/{MISSING_ID}/cover/", "gallery", Level.MANAGE),
    ("DELETE", f"/api/albums/{MISSING_ID}/cover/", "gallery", Level.OWNER),
    ("POST", "/api/photos/", "gallery", Level.MANAGE),
    ("PATCH", f"/api/photos/{MISSING_ID}/", "gallery", Level.MANAGE),
    ("DELETE", f"/api/photos/{MISSING_ID}/", "gallery", Level.OWNER),
    ("PUT", f"/api/albums/{MISSING_ID}/photos/order/", "gallery", Level.MANAGE),
    ("GET", "/api/gallery/trash/", "gallery", Level.OWNER),
    ("POST", f"/api/gallery/trash/albums/{MISSING_ID}/restore/", "gallery", Level.OWNER),
    ("POST", f"/api/gallery/trash/photos/{MISSING_ID}/restore/", "gallery", Level.OWNER),
]

_ALL_SCOPES = [
    "members",
    "schedule",
    "songs",
    "gallery",
    "events",
    "notices",
    "reports.hymnal_history",
]
ROLE_LEVELS: dict[Role, dict[str, Level]] = {
    Role.ADMIN: {scope: Level.OWNER for scope in _ALL_SCOPES},
    Role.LEADER: {
        "members": Level.MANAGE,
        "schedule": Level.MANAGE,
        "songs": Level.MANAGE,
        "gallery": Level.OWNER,
        "events": Level.MANAGE,
        "notices": Level.MANAGE,
        "reports.hymnal_history": Level.VIEW,
    },
    Role.MEDIA: {
        "gallery": Level.OWNER,
        "events": Level.MANAGE,
        "notices": Level.MANAGE,
        "reports.hymnal_history": Level.VIEW,
    },
}

CALLERS: dict[str, list[Role]] = {
    "admin": [Role.ADMIN],
    "leader": [Role.LEADER],
    "media": [Role.MEDIA],
    "none": [],
    "leader+media": [Role.LEADER, Role.MEDIA],
}


def _expected_level(roles: list[Role], scope: str) -> Level | None:
    levels = [ROLE_LEVELS[role][scope] for role in roles if scope in ROLE_LEVELS[role]]
    return max(levels) if levels else None


def _send(client: APIClient, method: str, url: str) -> int:
    response = getattr(client, method.lower())(url, {}, format="json")
    return int(response.status_code)


def _row_id(row: tuple[str, str, str, Level]) -> str:
    return f"{row[0]} {row[1]}"


@pytest.mark.django_db
@pytest.mark.parametrize("row", ENDPOINTS, ids=_row_id)
@pytest.mark.parametrize("caller", list(CALLERS))
def test_level_below_required_is_403(row: tuple[str, str, str, Level], caller: str) -> None:
    method, url, scope, required = row
    client, _ = make_role_client(*CALLERS[caller])
    held = _expected_level(CALLERS[caller], scope)

    status = _send(client, method, url)

    if held is None or held < required:
        assert status == 403, f"{caller} {method} {url} holds {held}, needs {required}"
    else:
        assert status not in (401, 403), f"{caller} {method} {url} was refused ({status})"


@pytest.mark.django_db
@pytest.mark.parametrize("row", ENDPOINTS, ids=_row_id)
def test_superuser_without_role_is_403(row: tuple[str, str, str, Level]) -> None:
    user = make_user(username="root")
    user.is_superuser = True
    user.is_staff = True
    user.save()
    client = APIClient()
    client.force_authenticate(user)
    assert _send(client, row[0], row[1]) == 403


@pytest.mark.django_db
@pytest.mark.parametrize("row", ENDPOINTS, ids=_row_id)
def test_anonymous_is_401(row: tuple[str, str, str, Level]) -> None:
    assert _send(APIClient(), row[0], row[1]) == 401


@pytest.mark.django_db
def test_leader_gets_403_on_every_delete() -> None:
    # Outside `gallery`, where Liderança holds owner since feature 013 (spec 012 SC-002).
    deletes = [row for row in ENDPOINTS if row[0] == "DELETE" and row[2] != "gallery"]
    assert deletes, "the classification lists DELETE endpoints"
    client, _ = make_role_client(Role.LEADER)
    for method, url, _, _ in deletes:
        assert _send(client, method, url) == 403, url


@pytest.mark.django_db
def test_admin_reaches_every_row_with_no_stored_permission() -> None:
    Group.objects.get(name=Role.ADMIN.value).permissions.clear()
    client, _ = make_role_client(Role.ADMIN)
    for method, url, _, _ in ENDPOINTS:
        assert _send(client, method, url) not in (401, 403), f"{method} {url}"
