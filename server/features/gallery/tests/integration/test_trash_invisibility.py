"""Regression: trashed items are invisible to every ordinary read and write
(specs/014-gallery-trash-sync US2, FR-006–FR-011)."""

import pytest
from rest_framework.test import APIClient

from conftest import make_member_client
from features.gallery.models.gallery import Album, Photo
from features.gallery.tests.integration.helpers import gallery_manager, image_file


class Tree:
    """P → A → B → C, a photo in each of A, B, C; A is then deleted. P has a live sibling S."""

    def __init__(self) -> None:
        self.manager = gallery_manager()
        self.member, _ = make_member_client()
        self.p = Album.objects.create(name="P")
        self.a = Album.objects.create(name="A", parent=self.p, cover_image="gallery/covers/a.jpg")
        self.s = Album.objects.create(name="S", parent=self.p, position=1)
        self.b = Album.objects.create(name="B", parent=self.a)
        self.c = Album.objects.create(name="C", parent=self.b)
        self.photos = [
            Photo.objects.create(album=album, name=f"{album.name}.jpg", image=f"x/{album.name}.jpg")
            for album in (self.a, self.b, self.c)
        ]
        assert self.manager.delete(f"/api/albums/{self.a.pk}/").status_code == 204


def _ids(client: APIClient, url: str) -> list[int]:
    return [item["id"] for item in client.get(url).data]


@pytest.mark.django_db
class TestReads:
    def test_album_and_photo_lists(self) -> None:
        tree = Tree()

        assert _ids(tree.member, "/api/albums/") == [tree.p.pk, tree.s.pk]
        assert _ids(tree.member, "/api/photos/") == []

    def test_album_photos_of_a_trashed_album_is_404(self) -> None:
        tree = Tree()

        for album in (tree.a, tree.b):
            assert tree.member.get(f"/api/albums/{album.pk}/photos/").status_code == 404

    def test_resolved_cover_never_comes_from_a_trashed_album(self) -> None:
        tree = Tree()

        parent = tree.member.get("/api/albums/").data[0]

        assert (parent["cover_url"], parent["cover_source_album_id"]) == (None, None)


@pytest.mark.django_db
class TestWritesUnderATrashedAlbum:
    def test_every_write_naming_it_is_404(self) -> None:
        tree = Tree()
        live_photo = Photo.objects.create(album=tree.s, name="s.jpg", image="x/s.jpg")
        client = tree.manager
        responses = [
            client.post("/api/albums/", {"name": "X", "parent_id": tree.a.pk}, format="json"),
            client.patch(f"/api/albums/{tree.s.pk}/", {"parent_id": tree.b.pk}, format="json"),
            client.patch(f"/api/photos/{live_photo.pk}/", {"album_id": tree.b.pk}, format="json"),
            client.post("/api/photos/", {"album_id": tree.c.pk, "image": image_file()}),
            client.put(f"/api/albums/{tree.a.pk}/cover/", {"image": image_file()}),
            client.delete(f"/api/albums/{tree.a.pk}/cover/"),
            client.patch(f"/api/albums/{tree.a.pk}/", {"name": "A2"}, format="json"),
            client.put("/api/albums/order/", {"parent_id": tree.a.pk, "ids": []}, format="json"),
        ]

        assert [r.status_code for r in responses] == [404] * len(responses)
        assert Photo.objects.get(pk=live_photo.pk).album_id == tree.s.pk

    def test_sibling_order_counts_live_albums_only(self) -> None:
        tree = Tree()
        url = "/api/albums/order/"

        ok = tree.manager.put(url, {"parent_id": tree.p.pk, "ids": [tree.s.pk]}, format="json")
        bad = tree.manager.put(
            url, {"parent_id": tree.p.pk, "ids": [tree.s.pk, tree.a.pk]}, format="json"
        )

        assert ok.status_code == 204
        assert bad.status_code == 400 and bad.data["unexpected"] == [tree.a.pk]


@pytest.mark.django_db
class TestAutomaticCover:
    def test_album_whose_photos_are_all_trashed_gets_the_automatic_cover(
        self, media_root: object
    ) -> None:
        album = Album.objects.create(name="Vazio")
        old = Photo.objects.create(album=album, name="old.jpg", image="x/old.jpg")
        client = gallery_manager()
        client.delete(f"/api/photos/{old.pk}/")

        response = client.post("/api/photos/", {"album_id": album.pk, "image": image_file()})

        assert response.status_code == 201
        assert (Album.objects.get(pk=album.pk).cover_image.name or "").startswith(
            f"gallery/covers/{album.pk}/"
        )
