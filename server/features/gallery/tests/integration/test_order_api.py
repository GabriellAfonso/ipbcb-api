"""Manual order of albums and photos (specs/013-gallery-write-api US5)."""

import pytest

from conftest import make_member_client
from features.gallery.models.gallery import Album, Photo
from features.gallery.tests.integration.helpers import gallery_manager

ALBUM_ORDER_URL = "/api/albums/order/"


def _photo_order_url(album: Album) -> str:
    return f"/api/albums/{album.pk}/photos/order/"


@pytest.mark.django_db
class TestAlbumOrder:
    def test_roots(self) -> None:
        first, second, third = (
            Album.objects.create(name=n, position=i) for i, n in enumerate("ABC")
        )

        response = gallery_manager().put(
            ALBUM_ORDER_URL,
            {"parent_id": None, "ids": [third.pk, first.pk, second.pk]},
            format="json",
        )

        assert response.status_code == 204
        client, _ = make_member_client()
        assert [a["name"] for a in client.get("/api/albums/").data] == ["C", "A", "B"]

    def test_children(self) -> None:
        parent = Album.objects.create(name="Retiros")
        older = Album.objects.create(name="2025", parent=parent, position=0)
        newer = Album.objects.create(name="2026", parent=parent, position=1)

        gallery_manager().put(
            ALBUM_ORDER_URL, {"parent_id": parent.pk, "ids": [newer.pk, older.pk]}, format="json"
        )

        newer.refresh_from_db()
        assert newer.position == 0

    def test_mismatch_is_400_with_the_lists(self) -> None:
        first = Album.objects.create(name="A", position=0)
        second = Album.objects.create(name="B", position=1)

        response = gallery_manager().put(
            ALBUM_ORDER_URL, {"parent_id": None, "ids": [second.pk, second.pk, 9999]}, format="json"
        )

        assert response.status_code == 400
        assert (
            response.data["missing"],
            response.data["unexpected"],
            response.data["repeated"],
        ) == (
            [first.pk],
            [9999],
            [second.pk],
        )
        first.refresh_from_db()
        assert first.position == 0

    def test_unknown_parent_is_404(self) -> None:
        response = gallery_manager().put(
            ALBUM_ORDER_URL, {"parent_id": 9999, "ids": []}, format="json"
        )

        assert response.status_code == 404


@pytest.mark.django_db
class TestPhotoOrder:
    def _photos(self, album: Album) -> list[Photo]:
        return [
            Photo.objects.create(album=album, name=f"{n}.jpg", image=f"x/{n}.jpg", position=i)
            for i, n in enumerate("abc")
        ]

    def test_applies_and_reads_back(self) -> None:
        album = Album.objects.create(name="Retiros")
        a, b, c = self._photos(album)

        response = gallery_manager().put(
            _photo_order_url(album), {"ids": [b.pk, c.pk, a.pk]}, format="json"
        )

        assert response.status_code == 204
        client, _ = make_member_client()
        names = [p["name"] for p in client.get(f"/api/albums/{album.pk}/photos/").data]
        assert names == ["b.jpg", "c.jpg", "a.jpg"]

    def test_photo_from_another_album_is_400(self) -> None:
        album = Album.objects.create(name="Retiros")
        a, b, c = self._photos(album)
        foreign = Photo.objects.create(
            album=Album.objects.create(name="Outro"), name="f.jpg", image="x/f"
        )

        response = gallery_manager().put(
            _photo_order_url(album), {"ids": [a.pk, b.pk, c.pk, foreign.pk]}, format="json"
        )

        assert response.status_code == 400
        assert response.data["unexpected"] == [foreign.pk]

    def test_empty_album_accepts_an_empty_list(self) -> None:
        album = Album.objects.create(name="Vazio")

        assert (
            gallery_manager().put(_photo_order_url(album), {"ids": []}, format="json").status_code
            == 204
        )

    def test_unknown_album_is_404(self) -> None:
        response = gallery_manager().put(
            "/api/albums/9999/photos/order/", {"ids": []}, format="json"
        )

        assert response.status_code == 404
