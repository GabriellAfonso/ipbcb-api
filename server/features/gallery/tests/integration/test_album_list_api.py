"""Members browse the album tree with resolved covers (specs/013-gallery-write-api US3)."""

import pytest

from conftest import make_member_client
from features.gallery.models.gallery import Album

ALBUMS_URL = "/api/albums/"


def _by_name() -> dict[str, dict[str, object]]:
    client, _ = make_member_client()
    response = client.get(ALBUMS_URL)
    assert response.status_code == 200
    return {album["name"]: album for album in response.data}


@pytest.mark.django_db
class TestAlbumList:
    def test_flat_list_in_tree_order_with_empty_albums(self) -> None:
        worship = Album.objects.create(name="Cultos", position=1)
        retreats = Album.objects.create(name="Retiros", position=0)
        Album.objects.create(name="2026", parent=retreats)

        client, _ = make_member_client()
        names = [(a["name"], a["parent_id"]) for a in client.get(ALBUMS_URL).data]

        assert names == [("Retiros", None), ("2026", retreats.pk), ("Cultos", None)]
        assert worship.pk

    def test_own_cover(self) -> None:
        album = Album.objects.create(name="Retiros", cover_image="gallery/covers/1/c.jpg")

        listed = _by_name()["Retiros"]

        assert listed["cover_source_album_id"] == album.pk
        assert str(listed["cover_url"]).endswith("/ipbcb/media/gallery/covers/1/c.jpg")

    def test_inherited_cover_is_depth_first(self) -> None:
        root = Album.objects.create(name="Retiros")
        year = Album.objects.create(name="2024", parent=root, position=0)
        saturday = Album.objects.create(
            name="Sábado", parent=year, cover_image="gallery/covers/s.jpg"
        )
        Album.objects.create(
            name="2025", parent=root, position=1, cover_image="gallery/covers/y.jpg"
        )

        listed = _by_name()

        assert listed["Retiros"]["cover_source_album_id"] == saturday.pk
        assert listed["2024"]["cover_source_album_id"] == saturday.pk

    def test_no_cover_anywhere(self) -> None:
        Album.objects.create(name="Retiros")

        listed = _by_name()["Retiros"]

        assert (listed["cover_url"], listed["cover_source_album_id"]) == (None, None)

    def test_a_changed_sub_album_cover_shows_on_the_next_list(self) -> None:
        root = Album.objects.create(name="Retiros")
        child = Album.objects.create(name="2026", parent=root, cover_image="gallery/covers/old.jpg")
        Album.objects.filter(pk=child.pk).update(cover_image="gallery/covers/new.jpg")

        assert str(_by_name()["Retiros"]["cover_url"]).endswith("gallery/covers/new.jpg")

    def test_query_count_does_not_grow_with_albums(
        self, django_assert_max_num_queries: object
    ) -> None:
        parent = None
        for index in range(50):
            parent = Album.objects.create(name=f"A{index}", parent=parent)
        client, _ = make_member_client()

        with django_assert_max_num_queries(12):  # type: ignore[operator]
            response = client.get(ALBUMS_URL)

        assert len(response.data) == 50
