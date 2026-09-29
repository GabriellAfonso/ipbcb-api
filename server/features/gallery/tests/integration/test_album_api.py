"""Building the album tree over the API (specs/013-gallery-write-api US2)."""

import pytest

from core.domain.access import Role
from features.gallery.models.gallery import Album, Photo
from features.gallery.tests.integration.helpers import gallery_manager

ALBUMS_URL = "/api/albums/"


def _detail(album: Album) -> str:
    return f"{ALBUMS_URL}{album.pk}/"


@pytest.mark.django_db
class TestCreate:
    def test_root_with_only_a_name(self) -> None:
        Album.objects.create(name="Cultos")

        response = gallery_manager(Role.LEADER, "leader").post(
            ALBUMS_URL, {"name": "Retiros"}, format="json"
        )

        assert response.status_code == 201
        assert response.data == {
            "id": response.data["id"],
            "name": "Retiros",
            "parent_id": None,
            "description": "",
            "event_date": None,
            "cover_url": None,
            "cover_source_album_id": None,
        }
        assert Album.objects.get(pk=response.data["id"]).position == 1

    def test_child_with_every_field(self) -> None:
        parent = Album.objects.create(name="Retiros")

        response = gallery_manager().post(
            ALBUMS_URL,
            {
                "name": "2026",
                "parent_id": parent.pk,
                "description": "Serra",
                "event_date": "2026-03-14",
            },
            format="json",
        )

        assert response.status_code == 201
        assert (response.data["parent_id"], response.data["event_date"]) == (
            parent.pk,
            "2026-03-14",
        )

    def test_regression_duplicate_root_name_is_400(self) -> None:
        Album.objects.create(name="Retiros")

        response = gallery_manager().post(ALBUMS_URL, {"name": "Retiros"}, format="json")

        assert response.status_code == 400
        assert "Retiros" in response.data["detail"]
        assert Album.objects.filter(name="Retiros").count() == 1

    def test_same_name_under_another_parent(self) -> None:
        retreats = Album.objects.create(name="Retiros")
        camps = Album.objects.create(name="Acampamentos")
        Album.objects.create(name="2025", parent=retreats)

        response = gallery_manager().post(
            ALBUMS_URL, {"name": "2025", "parent_id": camps.pk}, format="json"
        )

        assert response.status_code == 201

    def test_blank_name_is_400(self) -> None:
        assert gallery_manager().post(ALBUMS_URL, {"name": "  "}, format="json").status_code == 400

    def test_unknown_parent_is_404(self) -> None:
        response = gallery_manager().post(
            ALBUMS_URL, {"name": "x", "parent_id": 9999}, format="json"
        )

        assert response.status_code == 404


@pytest.mark.django_db
class TestPatch:
    def test_rename_keeps_every_file_path(self) -> None:
        album = Album.objects.create(name="Retiro", cover_image="gallery/covers/1/c.jpg")
        photo = Photo.objects.create(
            album=album, name="a.jpg", image="gallery/1/a.jpg", thumbnail="gallery/thumbs/1/a.jpg"
        )

        response = gallery_manager().patch(_detail(album), {"name": "Retiros"}, format="json")

        assert response.data["name"] == "Retiros"
        photo.refresh_from_db()
        album.refresh_from_db()
        assert (photo.image.name, photo.thumbnail.name, album.cover_image.name) == (
            "gallery/1/a.jpg",
            "gallery/thumbs/1/a.jpg",
            "gallery/covers/1/c.jpg",
        )

    def test_move_to_root_goes_last(self) -> None:
        Album.objects.create(name="Cultos", position=0)
        parent = Album.objects.create(name="Retiros", position=1)
        child = Album.objects.create(name="2026", parent=parent)

        response = gallery_manager().patch(_detail(child), {"parent_id": None}, format="json")

        child.refresh_from_db()
        assert response.data["parent_id"] is None
        assert child.position == 2

    def test_regression_cycle_is_400_and_changes_nothing(self) -> None:
        root = Album.objects.create(name="A")
        middle = Album.objects.create(name="B", parent=root)
        leaf = Album.objects.create(name="C", parent=middle)

        response = gallery_manager().patch(_detail(root), {"parent_id": leaf.pk}, format="json")

        assert response.status_code == 400
        assert (response.data["album_id"], response.data["parent_id"]) == (root.pk, leaf.pk)
        assert response.data["chain"] == [leaf.pk, middle.pk, root.pk]
        root.refresh_from_db()
        assert root.parent_id is None

    def test_regression_move_under_itself_is_400(self) -> None:
        album = Album.objects.create(name="A")

        response = gallery_manager().patch(_detail(album), {"parent_id": album.pk}, format="json")

        assert response.status_code == 400

    def test_rename_to_a_sibling_name_is_400(self) -> None:
        Album.objects.create(name="Cultos")
        album = Album.objects.create(name="Retiros")

        response = gallery_manager().patch(_detail(album), {"name": "Cultos"}, format="json")

        assert response.status_code == 400

    def test_clears_the_event_date(self) -> None:
        album = Album.objects.create(name="Retiros", event_date="2026-03-14")

        response = gallery_manager().patch(_detail(album), {"event_date": None}, format="json")

        assert response.data["event_date"] is None

    @pytest.mark.parametrize("body", [{"name": "x"}, {"parent_id": 9999}])
    def test_unknown_album_or_parent_is_404(self, body: dict[str, object]) -> None:
        album = Album.objects.create(name="Retiros")
        url = _detail(album) if "parent_id" in body else f"{ALBUMS_URL}9999/"

        assert gallery_manager().patch(url, body, format="json").status_code == 404
