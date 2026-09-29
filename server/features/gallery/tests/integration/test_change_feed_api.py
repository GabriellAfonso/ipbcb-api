"""The change feed through the API (specs/014-gallery-trash-sync US3, contract).

Runs on the real clock: rows written by the setup are moved an hour back, and cursors are built
with ``encode_cursor``, so each test controls what falls inside the 90 s overlap.
"""

from datetime import timedelta
from typing import Any

import pytest
from django.apps import apps
from django.core.management import call_command
from django.test import Client
from django.utils import timezone
from rest_framework.test import APIClient

from conftest import make_auth_client, make_member_client, make_role_client, make_user
from core.domain.access import Role
from features.gallery.domain.feed_cursor import encode_cursor
from features.gallery.models.gallery import Album, Photo
from features.gallery.models.tags import PhotoTag
from features.gallery.models.trash import GalleryDeletionBatch
from features.gallery.tests.integration.helpers import gallery_manager

FEED = "/api/gallery/changes/"


class Gallery:
    """Album A (photo pa1, pa2) with sub-album B (photo pb), all last changed an hour ago."""

    def __init__(self) -> None:
        self.member: APIClient = make_member_client()[0]
        self.manager = gallery_manager()
        self.a = Album.objects.create(name="A")
        self.b = Album.objects.create(name="B", parent=self.a)
        self.pa1 = Photo.objects.create(album=self.a, name="1.jpg", image="x/1.jpg", position=0)
        self.pa2 = Photo.objects.create(album=self.a, name="2.jpg", image="x/2.jpg", position=1)
        self.pb = Photo.objects.create(album=self.b, name="b.jpg", image="x/b.jpg")
        hour_ago = timezone.now() - timedelta(hours=1)
        Album.all_objects.update(updated_at=hour_ago)
        Photo.all_objects.update(updated_at=hour_ago)
        self.cursor = encode_cursor(timezone.now() - timedelta(minutes=10))

    def delta(self) -> dict[str, Any]:
        response = self.member.get(FEED, {"since": self.cursor})
        assert response.status_code == 200
        return dict(response.data)


def _ids(items: object) -> list[int]:
    return [item["id"] for item in items]  # type: ignore[attr-defined]


@pytest.mark.django_db
class TestFullSync:
    def test_everything_and_a_cursor(self) -> None:
        gallery = Gallery()

        body = gallery.member.get(FEED).data

        assert _ids(body["albums"]) == [gallery.a.pk, gallery.b.pk]
        assert _ids(body["photos"]) == [gallery.pa1.pk, gallery.pa2.pk, gallery.pb.pk]
        assert body["photos"][0]["position"] == 0 and "image_url" in body["photos"][0]
        assert (body["deleted_album_ids"], body["deleted_photo_ids"]) == ([], [])
        assert body["full_sync_required"] is False and body["cursor"].startswith("v1.")


@pytest.mark.django_db
class TestDelta:
    def test_nothing_changed(self) -> None:
        body = Gallery().delta()

        assert (body["albums"], body["photos"]) == ([], [])

    def test_create_and_rename(self) -> None:
        gallery = Gallery()
        created = gallery.manager.post("/api/albums/", {"name": "C"}, format="json").data
        gallery.manager.patch(f"/api/photos/{gallery.pa1.pk}/", {"name": "x.jpg"}, format="json")

        body = gallery.delta()

        assert _ids(body["albums"]) == [created["id"]]
        assert _ids(body["photos"]) == [gallery.pa1.pk]

    def test_album_delete_lists_sub_albums_and_every_photo(self) -> None:
        gallery = Gallery()
        gallery.manager.delete(f"/api/albums/{gallery.a.pk}/")

        body = gallery.delta()

        assert body["deleted_album_ids"] == [gallery.a.pk, gallery.b.pk]
        assert body["deleted_photo_ids"] == sorted([gallery.pa1.pk, gallery.pa2.pk, gallery.pb.pk])

    def test_rename_lists_the_album_and_its_photos(self) -> None:
        gallery = Gallery()
        gallery.manager.patch(f"/api/albums/{gallery.b.pk}/", {"name": "B2"}, format="json")

        body = gallery.delta()

        assert _ids(body["albums"]) == [gallery.b.pk]
        assert _ids(body["photos"]) == [gallery.pb.pk]
        assert body["photos"][0]["album_name"] == "B2"

    def test_reorder_lists_only_the_moved_photos_with_their_position(self) -> None:
        gallery = Gallery()
        third = Photo.objects.create(album=gallery.a, name="3.jpg", image="x/3.jpg", position=2)
        Photo.all_objects.filter(pk=third.pk).update(updated_at=timezone.now() - timedelta(hours=1))
        ids = [gallery.pa2.pk, gallery.pa1.pk, third.pk]
        gallery.manager.put(
            f"/api/albums/{gallery.a.pk}/photos/order/", {"ids": ids}, format="json"
        )

        body = gallery.delta()

        assert {(p["id"], p["position"]) for p in body["photos"]} == {
            (gallery.pa2.pk, 0),
            (gallery.pa1.pk, 1),
        }

    def test_sub_album_cover_change_lists_the_ancestor(self) -> None:
        gallery = Gallery()
        Album.all_objects.filter(pk=gallery.b.pk).update(cover_image="gallery/covers/b/old.jpg")
        gallery.manager.delete(f"/api/albums/{gallery.b.pk}/cover/")

        body = gallery.delta()

        assert set(_ids(body["albums"])) == {gallery.a.pk, gallery.b.pk}

    def test_restore_reappears_as_changed(self) -> None:
        gallery = Gallery()
        gallery.manager.delete(f"/api/photos/{gallery.pb.pk}/")
        gallery.manager.post(f"/api/gallery/trash/photos/{gallery.pb.pk}/restore/")

        body = gallery.delta()

        assert _ids(body["photos"]) == [gallery.pb.pk]
        assert body["deleted_photo_ids"] == []

    def test_regression_deleted_id_survives_the_purge(self, media_root: object) -> None:
        gallery = Gallery()
        gallery.manager.delete(f"/api/photos/{gallery.pb.pk}/")
        month_ago = timezone.now() - timedelta(days=31)
        GalleryDeletionBatch.objects.update(deleted_at=month_ago)

        call_command("purge_gallery_trash")

        assert not Photo.all_objects.filter(pk=gallery.pb.pk).exists()
        assert gallery.delta()["deleted_photo_ids"] == [gallery.pb.pk]


@pytest.mark.django_db
class TestFullSyncRequired:
    @pytest.mark.parametrize("since", ["garbage", "v2.AAAA"])
    def test_unreadable_cursor(self, since: str) -> None:
        body = Gallery().member.get(FEED, {"since": since}).data

        assert body["full_sync_required"] is True
        assert (body["albums"], body["photos"]) == ([], [])

    def test_cursor_older_than_ninety_days(self) -> None:
        gallery = Gallery()
        old = encode_cursor(timezone.now() - timedelta(days=91))

        assert gallery.member.get(FEED, {"since": old}).data["full_sync_required"] is True


@pytest.mark.django_db
def test_non_member_is_403() -> None:
    assert make_auth_client(make_user(username="outsider")).get(FEED).status_code == 403


def _tagged_gallery() -> tuple[Gallery, Any, Any]:
    """The Gallery with Ana tagged in pa1 and pb, Bruno tagged nowhere; rows an hour old."""
    gallery = Gallery()
    member = apps.get_model("members", "Member")
    ana = member.objects.create(name="Ana")
    bruno = member.objects.create(name="Bruno")
    PhotoTag.objects.bulk_create(
        [PhotoTag(photo=gallery.pa1, member=ana), PhotoTag(photo=gallery.pb, member=ana)]
    )
    Photo.all_objects.update(updated_at=timezone.now() - timedelta(hours=1))
    return gallery, ana, bruno


def _staff_admin() -> Client:
    """A Django admin session (the admin paths bypass the members API)."""
    user = make_user(username="staff")
    user.is_staff = user.is_superuser = True
    user.save()
    client = Client()
    client.force_login(user)
    return client


@pytest.mark.django_db
class TestMemberTagsInTheFeed:
    """specs/015-gallery-member-tags US5, FR-025–FR-028."""

    def test_tag_write_returns_only_the_changed_photos(self) -> None:
        gallery, ana, _ = _tagged_gallery()
        body = {
            "photo_ids": [gallery.pa1.pk, gallery.pa2.pk],
            "add_member_ids": [ana.pk],
        }
        gallery.manager.post("/api/photos/members/", body, format="json")

        delta = gallery.delta()

        assert _ids(delta["photos"]) == [gallery.pa2.pk]
        assert _ids(delta["photos"][0]["members"]) == [ana.pk]

    def test_regression_rename_through_the_api_returns_the_member_s_photos(self) -> None:
        gallery, ana, _ = _tagged_gallery()
        admin = make_role_client(Role.ADMIN, username="roll_admin")[0]
        admin.patch(f"/api/admin/members/{ana.pk}/", {"name": "Ana Maria"}, format="json")

        delta = gallery.delta()

        assert _ids(delta["photos"]) == [gallery.pa1.pk, gallery.pb.pk]
        assert {m["name"] for p in delta["photos"] for m in p["members"]} == {"Ana Maria"}

    def test_delete_through_the_api_returns_the_photos_without_the_member(self) -> None:
        gallery, ana, _ = _tagged_gallery()
        admin = make_role_client(Role.ADMIN, username="roll_admin")[0]
        assert admin.delete(f"/api/admin/members/{ana.pk}/").status_code == 204

        delta = gallery.delta()

        assert _ids(delta["photos"]) == [gallery.pa1.pk, gallery.pb.pk]
        assert all(p["members"] == [] for p in delta["photos"])

    def test_rename_in_the_django_admin_is_seen_too(self) -> None:
        gallery, ana, _ = _tagged_gallery()
        response = _staff_admin().post(
            f"/admin/members/member/{ana.pk}/change/",
            {"name": "Ana Admin", "first_name": "", "last_name": "", "is_active": "on"},
        )
        assert response.status_code == 302

        assert _ids(gallery.delta()["photos"]) == [gallery.pa1.pk, gallery.pb.pk]

    def test_bulk_delete_in_the_django_admin_is_seen_too(self) -> None:
        gallery, ana, _ = _tagged_gallery()
        response = _staff_admin().post(
            "/admin/members/member/",
            {"action": "delete_selected", "_selected_action": [ana.pk], "post": "yes"},
        )
        assert response.status_code == 302

        assert _ids(gallery.delta()["photos"]) == [gallery.pa1.pk, gallery.pb.pk]

    def test_untagged_member_or_another_field_returns_nothing(self) -> None:
        gallery, ana, bruno = _tagged_gallery()
        admin = make_role_client(Role.ADMIN, username="roll_admin")[0]
        admin.patch(f"/api/admin/members/{bruno.pk}/", {"name": "Bruno Lima"}, format="json")
        admin.patch(f"/api/admin/members/{ana.pk}/", {"first_name": "Ana"}, format="json")

        assert gallery.delta()["photos"] == []

    def test_trashed_photo_waits_for_its_restore(self) -> None:
        gallery, ana, _ = _tagged_gallery()
        gallery.manager.delete(f"/api/photos/{gallery.pb.pk}/")
        ana.name = "Ana Maria"
        ana.save()

        first = gallery.delta()
        gallery.manager.post(f"/api/gallery/trash/photos/{gallery.pb.pk}/restore/")
        second = gallery.delta()

        assert _ids(first["photos"]) == [gallery.pa1.pk]
        restored = {p["id"]: p for p in second["photos"]}[gallery.pb.pk]
        assert restored["members"][0]["name"] == "Ana Maria"
