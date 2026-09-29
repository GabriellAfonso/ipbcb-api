"""Every gallery endpoint x every kind of caller (specs/013-gallery-write-api FR-001-FR-003,
SC-007).

Reads need membership only. Writes need a level on ``gallery``; Admin, Liderança and Mídia all
hold ``owner``, so every write — ``DELETE`` of a cover included — is open to the three roles and
closed to a member without a role. Permission is checked before existence, so the write rows use
ids that do not exist: an allowed caller gets past the permission (404/400), a refused one 403.
"""

from collections.abc import Callable

import pytest
from rest_framework.test import APIClient

from conftest import make_auth_client, make_member_client, make_role_client, make_user
from core.domain.access import Role
from features.gallery.models.gallery import Album

MISSING = 999_999

READS = [
    "/api/photos/",
    "/api/albums/",
    "/api/albums/{album}/photos/",
    "/api/gallery/changes/",
    # specs/015-gallery-member-tags: the tagged-member list and the filter are member reads.
    "/api/gallery/tagged-members/",
    "/api/photos/?member_id=1",
]

WRITES = [
    ("POST", "/api/albums/"),
    ("PATCH", f"/api/albums/{MISSING}/"),
    ("PUT", "/api/albums/order/"),
    ("PUT", f"/api/albums/{MISSING}/cover/"),
    ("DELETE", f"/api/albums/{MISSING}/cover/"),
    ("POST", "/api/photos/"),
    ("PATCH", f"/api/photos/{MISSING}/"),
    ("PUT", f"/api/albums/{MISSING}/photos/order/"),
    # specs/014-gallery-trash-sync: DELETE at the default owner, restore at an owner override.
    ("DELETE", f"/api/albums/{MISSING}/"),
    ("DELETE", f"/api/photos/{MISSING}/"),
    ("POST", f"/api/gallery/trash/albums/{MISSING}/restore/"),
    ("POST", f"/api/gallery/trash/photos/{MISSING}/restore/"),
    # specs/015-gallery-member-tags: tag writes at the default manage.
    ("PUT", f"/api/photos/{MISSING}/members/"),
    ("POST", "/api/photos/members/"),
]


def _anonymous() -> APIClient:
    return APIClient()


def _non_member() -> APIClient:
    return make_auth_client(make_user(username="outsider"))


def _member() -> APIClient:
    return make_member_client()[0]


def _role(role: Role) -> Callable[[], APIClient]:
    return lambda: make_role_client(role, username=f"{role.value}_holder")[0]


ROLE_CALLERS = {
    "admin": _role(Role.ADMIN),
    "leader": _role(Role.LEADER),
    "media": _role(Role.MEDIA),
}


MULTIPART = {("PUT", f"/api/albums/{MISSING}/cover/"), ("POST", "/api/photos/")}


def _send(client: APIClient, method: str, url: str) -> int:
    body_format = "multipart" if (method, url) in MULTIPART else "json"
    return int(getattr(client, method.lower())(url, {}, format=body_format).status_code)


@pytest.mark.django_db
class TestReads:
    @pytest.mark.parametrize("url", READS)
    def test_member_reads(self, url: str) -> None:
        album = Album.objects.create(name="Retiros")
        assert _member().get(url.format(album=album.pk)).status_code == 200

    @pytest.mark.parametrize("url", READS)
    @pytest.mark.parametrize("caller", ["anonymous", "non_member", *ROLE_CALLERS])
    def test_others_cannot_read(self, url: str, caller: str) -> None:
        # A role never grants membership (spec 012 FR-011).
        album = Album.objects.create(name="Retiros")
        make = {"anonymous": _anonymous, "non_member": _non_member, **ROLE_CALLERS}[caller]
        expected = 401 if caller == "anonymous" else 403

        assert make().get(url.format(album=album.pk)).status_code == expected


@pytest.mark.django_db
class TestWrites:
    @pytest.mark.parametrize(("method", "url"), WRITES)
    @pytest.mark.parametrize("caller", list(ROLE_CALLERS))
    def test_every_role_may_write(self, method: str, url: str, caller: str) -> None:
        assert _send(ROLE_CALLERS[caller](), method, url) in (400, 404)

    @pytest.mark.parametrize(("method", "url"), WRITES)
    def test_member_without_role_may_not(self, method: str, url: str) -> None:
        assert _send(_member(), method, url) == 403

    @pytest.mark.parametrize(("method", "url"), WRITES)
    def test_anonymous_is_401(self, method: str, url: str) -> None:
        assert _send(_anonymous(), method, url) == 401


@pytest.mark.django_db
class TestTrashList:
    """GET with an ``owner`` override (spec 014 FR-013): the three roles, never a plain member."""

    @pytest.mark.parametrize("caller", list(ROLE_CALLERS))
    def test_every_role_reads_the_trash(self, caller: str) -> None:
        assert ROLE_CALLERS[caller]().get("/api/gallery/trash/").status_code == 200

    def test_member_without_role_may_not(self) -> None:
        assert _member().get("/api/gallery/trash/").status_code == 403

    def test_anonymous_is_401(self) -> None:
        assert _anonymous().get("/api/gallery/trash/").status_code == 401


@pytest.mark.django_db
class TestTagPicker:
    """GET with a ``manage`` override (spec 015 FR-020, FR-030): the three roles, never a plain
    member."""

    @pytest.mark.parametrize("caller", list(ROLE_CALLERS))
    def test_every_role_reads_the_picker(self, caller: str) -> None:
        assert ROLE_CALLERS[caller]().get("/api/gallery/taggable-members/").status_code == 200

    def test_member_without_role_may_not(self) -> None:
        assert _member().get("/api/gallery/taggable-members/").status_code == 403

    def test_anonymous_is_401(self) -> None:
        assert _anonymous().get("/api/gallery/taggable-members/").status_code == 401

    def test_regression_media_reaches_the_picker_but_not_the_roll(self) -> None:
        """The picker is the one exception to spec 012 User Story 3: a Mídia user who is not
        flagged a member reads names there and is still refused the member list, the management
        endpoints and a members/ file (spec 015 FR-031)."""
        media = _role(Role.MEDIA)()

        assert media.get("/api/gallery/taggable-members/").status_code == 200
        assert media.get("/api/members/").status_code == 403
        assert media.get("/api/admin/members/").status_code == 403
        # Permission is checked before existence (spec 009), so a missing file still says 403.
        assert media.get("/ipbcb/media/members/x.jpg").status_code == 403
