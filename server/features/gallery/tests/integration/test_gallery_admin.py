"""The Django admin obeys the same album rules as the API (specs/013-gallery-write-api FR-005,
FR-006, research R-11)."""

import pytest
from django.test import Client
from django.utils import timezone

from features.accounts.models.user import User
from features.gallery.models.gallery import Album, Photo

ADD_URL = "/admin/gallery/album/add/"


def _change_url(album: Album) -> str:
    return f"/admin/gallery/album/{album.pk}/change/"


def _form(name: str, parent: Album | None = None) -> dict[str, object]:
    return {
        "name": name,
        "parent": parent.pk if parent else "",
        "description": "",
        "event_date": "",
    }


@pytest.fixture
def admin_client() -> Client:
    client = Client()
    client.force_login(User.objects.create_superuser(username="site_admin", password="pass12345"))
    return client


@pytest.mark.django_db
class TestAlbumAdmin:
    def test_add_goes_last_among_siblings(self, admin_client: Client) -> None:
        Album.objects.create(name="Cultos", position=4)

        response = admin_client.post(ADD_URL, _form("Retiros"))

        assert response.status_code == 302
        assert Album.objects.get(name="Retiros").position == 5

    def test_duplicate_root_name_is_refused(self, admin_client: Client) -> None:
        Album.objects.create(name="Retiros")

        response = admin_client.post(ADD_URL, _form("Retiros"))

        assert response.status_code == 200
        assert Album.objects.filter(name="Retiros").count() == 1

    def test_cycle_is_refused(self, admin_client: Client) -> None:
        root = Album.objects.create(name="A")
        child = Album.objects.create(name="B", parent=root)

        response = admin_client.post(_change_url(root), _form("A", parent=child))

        assert response.status_code == 200
        assert "dentro" in response.content.decode()
        root.refresh_from_db()
        assert root.parent_id is None

    def test_move_goes_last_in_the_new_parent(self, admin_client: Client) -> None:
        parent = Album.objects.create(name="Retiros")
        Album.objects.create(name="2025", parent=parent, position=0)
        moved = Album.objects.create(name="2026")

        admin_client.post(_change_url(moved), _form("2026", parent=parent))

        moved.refresh_from_db()
        assert (moved.parent_id, moved.position) == (parent.pk, 1)

    def test_album_with_a_child_cannot_be_deleted(self, admin_client: Client) -> None:
        parent = Album.objects.create(name="Retiros")
        Album.objects.create(name="2026", parent=parent)

        admin_client.post(f"/admin/gallery/album/{parent.pk}/delete/", {"post": "yes"})

        assert Album.objects.filter(pk=parent.pk).exists()


@pytest.mark.django_db
class TestPhotoAdmin:
    def test_photos_cannot_be_added_outside_the_upload_page(self, admin_client: Client) -> None:
        assert admin_client.get("/admin/gallery/photo/add/").status_code == 403

    def test_files_are_read_only(self, admin_client: Client) -> None:
        album = Album.objects.create(name="Retiros")
        photo = Photo.objects.create(album=album, name="a.jpg", image="gallery/1/a.jpg")

        admin_client.post(
            f"/admin/gallery/photo/{photo.pk}/change/",
            {
                "album": album.pk,
                "name": "b.jpg",
                "description": "",
                "date_taken": "",
                "image": "x.jpg",
            },
        )

        photo.refresh_from_db()
        assert (photo.name, photo.image.name) == ("b.jpg", "gallery/1/a.jpg")


def _trash(album: Album) -> None:
    Album.all_objects.filter(pk=album.pk).update(deleted_at=timezone.now())


@pytest.mark.django_db
class TestNoDeleteInTheAdmin:
    """specs/014-gallery-trash-sync FR-012: deleting lives in the app, through the trash."""

    @pytest.mark.parametrize("model", ["album", "photo"])
    def test_delete_url_is_refused(self, admin_client: Client, model: str) -> None:
        album = Album.objects.create(name="Retiros")
        photo = Photo.objects.create(album=album, name="a.jpg", image="gallery/1/a.jpg")
        pk = album.pk if model == "album" else photo.pk

        get = admin_client.get(f"/admin/gallery/{model}/{pk}/delete/")
        post = admin_client.post(f"/admin/gallery/{model}/{pk}/delete/", {"post": "yes"})

        assert (get.status_code, post.status_code) == (403, 403)
        assert (
            Album.objects.filter(pk=album.pk).exists()
            and Photo.objects.filter(pk=photo.pk).exists()
        )

    @pytest.mark.parametrize("model", ["album", "photo"])
    def test_changelist_has_no_bulk_delete(self, admin_client: Client, model: str) -> None:
        response = admin_client.get(f"/admin/gallery/{model}/")

        assert "delete_selected" not in response.content.decode()

    def test_change_page_has_no_delete_link(self, admin_client: Client) -> None:
        album = Album.objects.create(name="Retiros")

        response = admin_client.get(_change_url(album))

        assert f"/admin/gallery/album/{album.pk}/delete/" not in response.content.decode()


@pytest.mark.django_db
class TestTrashedAlbumsHiddenInTheAdmin:
    def test_changelist_parent_choices_and_upload_page(self, admin_client: Client) -> None:
        Album.objects.create(name="Vivo")
        gone = Album.objects.create(name="NaLixeira")
        _trash(gone)

        changelist = admin_client.get("/admin/gallery/album/").content.decode()
        add_form = admin_client.get(ADD_URL).content.decode()
        upload = admin_client.get("/admin/gallery/album/upload/").content.decode()

        for page in (changelist, add_form, upload):
            assert "Vivo" in page
            assert "NaLixeira" not in page

    def test_photo_edit_marks_it_changed_for_the_feed(self, admin_client: Client) -> None:
        album = Album.objects.create(name="Retiros")
        photo = Photo.objects.create(album=album, name="a.jpg", image="gallery/1/a.jpg")
        before = Photo.objects.get(pk=photo.pk).updated_at

        admin_client.post(
            f"/admin/gallery/photo/{photo.pk}/change/",
            {"album": album.pk, "name": "b.jpg", "description": "", "date_taken": ""},
        )

        assert Photo.objects.get(pk=photo.pk).updated_at > before
