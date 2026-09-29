"""Delete to the trash, list it, restore from it, through the API
(specs/014-gallery-trash-sync US1, US2, US4; contracts/gallery-trash-api.md)."""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.test import APIClient

from conftest import make_member_client
from core.domain.access import Role
from features.gallery.models.gallery import Album, Photo
from features.gallery.models.trash import GalleryDeletionBatch, GalleryDeletionMark
from features.gallery.tests.integration.helpers import gallery_manager

TRASH_URL = "/api/gallery/trash/"


def _photo(album: Album, name: str = "a.jpg", position: int = 0) -> Photo:
    return Photo.objects.create(
        album=album,
        name=name,
        image=f"gallery/{album.pk}/{name}",
        thumbnail=f"gallery/thumbs/{album.pk}/{name}",
        position=position,
    )


def _restore(client: APIClient, kind: str, item_id: int) -> Response:
    return client.post(f"{TRASH_URL}{kind}s/{item_id}/restore/")


@pytest.mark.django_db
class TestDeletePhoto:
    def test_photo_goes_to_the_trash_and_leaves_every_read(self) -> None:
        album = Album.objects.create(name="Culto")
        photo = _photo(album)
        member, _ = make_member_client()

        response = gallery_manager().delete(f"/api/photos/{photo.pk}/")

        assert response.status_code == 204
        assert member.get("/api/photos/").data == []
        assert member.get(f"/api/albums/{album.pk}/photos/").data == []
        kept = Photo.all_objects.get(pk=photo.pk)
        assert kept.deleted_at is not None and kept.image.name == photo.image.name
        assert GalleryDeletionMark.objects.filter(kind="photo", object_id=photo.pk).exists()

    def test_second_delete_is_404(self) -> None:
        photo = _photo(Album.objects.create(name="Culto"))
        client = gallery_manager()
        client.delete(f"/api/photos/{photo.pk}/")

        response = client.delete(f"/api/photos/{photo.pk}/")

        assert response.status_code == 404
        assert response.data["photo_id"] == photo.pk
        assert GalleryDeletionBatch.objects.count() == 1

    def test_trashed_photo_cannot_be_edited_or_ordered(self) -> None:
        album = Album.objects.create(name="Culto")
        gone, kept = _photo(album, "gone.jpg"), _photo(album, "kept.jpg", position=1)
        client = gallery_manager()
        client.delete(f"/api/photos/{gone.pk}/")

        patch = client.patch(f"/api/photos/{gone.pk}/", {"name": "x.jpg"}, format="json")
        order = client.put(
            f"/api/albums/{album.pk}/photos/order/", {"ids": [gone.pk, kept.pk]}, format="json"
        )

        assert patch.status_code == 404
        assert order.status_code == 400 and order.data["unexpected"] == [gone.pk]


@pytest.mark.django_db
class TestDeleteAlbum:
    def test_subtree_shares_one_batch_and_files_stay(self) -> None:
        root = Album.objects.create(name="A")
        child = Album.objects.create(name="B", parent=root)
        photos = [_photo(root), _photo(child)]

        response = gallery_manager().delete(f"/api/albums/{root.pk}/")

        assert response.status_code == 204
        batches = {
            Album.all_objects.get(pk=root.pk).deletion_batch_id,
            Album.all_objects.get(pk=child.pk).deletion_batch_id,
            *(Photo.all_objects.get(pk=p.pk).deletion_batch_id for p in photos),
        }
        assert len(batches) == 1 and None not in batches
        assert Photo.all_objects.count() == 2

    def test_unknown_or_trashed_album_is_404(self) -> None:
        album = Album.objects.create(name="A")
        client = gallery_manager()
        client.delete(f"/api/albums/{album.pk}/")

        again = client.delete(f"/api/albums/{album.pk}/")
        unknown = client.delete("/api/albums/999999/")

        assert (again.status_code, unknown.status_code) == (404, 404)
        assert again.data["album_id"] == album.pk

    def test_regression_name_is_free_after_delete(self) -> None:
        parent = Album.objects.create(name="P")
        culto = Album.objects.create(name="Culto", parent=parent)
        root_culto = Album.objects.create(name="Culto")
        client = gallery_manager()
        client.delete(f"/api/albums/{culto.pk}/")
        client.delete(f"/api/albums/{root_culto.pk}/")

        child = client.post(
            "/api/albums/", {"name": "Culto", "parent_id": parent.pk}, format="json"
        )
        root = client.post("/api/albums/", {"name": "Culto"}, format="json")

        assert (child.status_code, root.status_code) == (201, 201)


@pytest.mark.django_db
class TestTrashListing:
    def test_one_entry_per_batch_per_contract(self) -> None:
        album = Album.objects.create(name="A", cover_image="gallery/covers/1/c.jpg")
        child = Album.objects.create(name="B", parent=album)
        p1 = _photo(album, "p1.jpg")
        _photo(album, "p2.jpg", 1)
        _photo(child, "p3.jpg")
        client = gallery_manager(Role.MEDIA, "media_deleter")
        client.delete(f"/api/photos/{p1.pk}/")
        client.delete(f"/api/albums/{album.pk}/")

        entries = client.get(TRASH_URL).data

        assert [(e["kind"], e["id"]) for e in entries] == [("album", album.pk), ("photo", p1.pk)]
        album_entry = entries[0]
        assert (album_entry["sub_album_count"], album_entry["photo_count"]) == (1, 2)
        assert album_entry["deleted_by"] == "media_deleter"
        assert album_entry["uploaded_by"] is None
        assert album_entry["thumbnail_url"].endswith("/ipbcb/media/gallery/covers/1/c.jpg")
        assert album_entry["purge_on"] == str((timezone.now() + timedelta(days=30)).date())
        assert entries[1]["thumbnail_url"].endswith(f"gallery/thumbs/{album.pk}/p1.jpg")

    def test_empty_trash(self) -> None:
        assert gallery_manager().get(TRASH_URL).data == []


@pytest.mark.django_db
class TestRestore:
    def test_regression_exact_batch_restore(self) -> None:
        album = Album.objects.create(name="A")
        child = Album.objects.create(name="B", parent=album, position=3)
        p1, p2 = _photo(album, "p1.jpg"), _photo(album, "p2.jpg", 5)
        client = gallery_manager()
        client.delete(f"/api/photos/{p1.pk}/")
        client.delete(f"/api/albums/{album.pk}/")

        response = _restore(client, "album", album.pk)

        assert response.status_code == 200 and response.data["id"] == album.pk
        assert set(Album.objects.values_list("pk", flat=True)) == {album.pk, child.pk}
        assert list(Photo.objects.values_list("pk", "position")) == [(p2.pk, 5)]
        assert Album.objects.get(pk=child.pk).position == 3
        assert Photo.all_objects.get(pk=p1.pk).deleted_at is not None
        assert [e["id"] for e in client.get(TRASH_URL).data] == [p1.pk]

    def test_restored_album_is_a_cover_source_again(self) -> None:
        parent = Album.objects.create(name="P")
        child = Album.objects.create(name="C", parent=parent, cover_image="gallery/covers/9/c.jpg")
        client = gallery_manager()
        client.delete(f"/api/albums/{child.pk}/")
        assert client.get("/api/albums/").data[0]["cover_source_album_id"] is None

        _restore(client, "album", child.pk)

        assert client.get("/api/albums/").data[0]["cover_source_album_id"] == child.pk

    def test_not_restorable_is_404(self) -> None:
        album = Album.objects.create(name="A")
        child = Album.objects.create(name="B", parent=album)
        photo = _photo(album)
        client = gallery_manager()
        live = _restore(client, "album", album.pk)
        client.delete(f"/api/albums/{album.pk}/")

        member_of_batch = _restore(client, "album", child.pk)
        cascaded_photo = _restore(client, "photo", photo.pk)

        assert (live.status_code, member_of_batch.status_code, cascaded_photo.status_code) == (
            404,
            404,
            404,
        )
        assert (member_of_batch.data["kind"], member_of_batch.data["id"]) == ("album", child.pk)

    def test_name_conflict_body_then_success_after_rename(self) -> None:
        parent = Album.objects.create(name="P")
        culto = Album.objects.create(name="Culto", parent=parent)
        client = gallery_manager()
        client.delete(f"/api/albums/{culto.pk}/")
        rival = client.post(
            "/api/albums/", {"name": "Culto", "parent_id": parent.pk}, format="json"
        )

        refused = _restore(client, "album", culto.pk)

        assert refused.status_code == 400
        assert refused.data["error_code"] == "VALIDATION_ERROR"
        assert refused.data["conflicting_album_id"] == rival.data["id"]
        assert "Renomeie" in refused.data["detail"]

        client.patch(f"/api/albums/{rival.data['id']}/", {"name": "Culto 2"}, format="json")
        assert _restore(client, "album", culto.pk).status_code == 200

    def test_trashed_parent_body_then_success_after_parent(self) -> None:
        album = Album.objects.create(name="A")
        photo = _photo(album)
        client = gallery_manager()
        client.delete(f"/api/photos/{photo.pk}/")
        client.delete(f"/api/albums/{album.pk}/")

        refused = _restore(client, "photo", photo.pk)

        assert refused.status_code == 400
        assert (refused.data["kind"], refused.data["trashed_parent_id"]) == ("photo", album.pk)
        assert _restore(client, "album", album.pk).status_code == 200
        restored = _restore(client, "photo", photo.pk)
        assert restored.status_code == 200 and restored.data["album_id"] == album.pk
