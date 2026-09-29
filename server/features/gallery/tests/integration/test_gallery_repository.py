from datetime import date

import pytest

from conftest import make_user
from features.gallery.dtos.gallery_dtos import NewPhoto
from features.gallery.models.gallery import Album, Photo
from features.gallery.repositories.gallery_repository import GalleryRepositoryImpl

REPO = GalleryRepositoryImpl()


def _new(album: Album, name: str = "a.jpg", thumbnail: str = "gallery/thumbs/1/t.jpg") -> NewPhoto:
    return NewPhoto(
        album_id=album.pk,
        image_name=f"gallery/{album.pk}/{name}",
        thumbnail_name=thumbnail,
        name=name,
        date_taken=date(2026, 3, 14),
        uploader_id=None,
    )


@pytest.mark.django_db
class TestCreatePhoto:
    def test_appends_and_maps_the_view(self) -> None:
        album = Album.objects.create(name="Retiros")

        first = REPO.create_photo(_new(album, "a.jpg"))
        second = REPO.create_photo(_new(album, "b.jpg"))

        positions = list(Photo.objects.order_by("id").values_list("position", flat=True))
        assert positions == [0, 1]
        assert (second.album_id, second.album_name, second.date_taken) == (
            album.pk,
            "Retiros",
            date(2026, 3, 14),
        )
        assert first.image_path == f"/ipbcb/media/gallery/{album.pk}/a.jpg"
        assert first.thumbnail_path == "/ipbcb/media/gallery/thumbs/1/t.jpg"

    def test_records_the_uploader(self) -> None:
        album = Album.objects.create(name="Retiros")
        user = make_user(username="uploader")

        photo = REPO.create_photo(_new(album).model_copy(update={"uploader_id": user.pk}))

        assert Photo.objects.get(pk=photo.id).uploaded_by_id == user.pk


@pytest.mark.django_db
class TestReads:
    def test_by_album_in_position_order_without_thumbnail(self) -> None:
        album = Album.objects.create(name="Retiros")
        other = Album.objects.create(name="Cultos")
        Photo.objects.create(album=album, name="second.jpg", image="x/2.jpg", position=1)
        Photo.objects.create(album=album, name="first.jpg", image="x/1.jpg", position=0)
        Photo.objects.create(album=other, name="other.jpg", image="x/3.jpg")

        photos = REPO.list_photos_by_album(album.pk)

        assert [p.name for p in photos] == ["first.jpg", "second.jpg"]
        assert photos[0].thumbnail_path is None

    def test_get_photo_missing(self) -> None:
        assert REPO.get_photo(999) is None


@pytest.mark.django_db
class TestWrites:
    def test_move_appends_to_the_target(self) -> None:
        source = Album.objects.create(name="A")
        target = Album.objects.create(name="B")
        Photo.objects.create(album=target, name="t.jpg", image="x/t.jpg", position=4)
        moved = Photo.objects.create(album=source, name="m.jpg", image="x/m.jpg")

        REPO.move_photo(moved.pk, target.pk)

        moved.refresh_from_db()
        assert (moved.album_id, moved.position, moved.image.name) == (target.pk, 5, "x/m.jpg")

    def test_apply_order(self) -> None:
        album = Album.objects.create(name="A")
        first, second = (
            Photo.objects.create(album=album, name=n, image=f"x/{n}") for n in ("1.jpg", "2.jpg")
        )

        REPO.apply_order([second.pk, first.pk])

        assert REPO.photo_ids(album.pk) == [second.pk, first.pk]

    def test_update_fields(self) -> None:
        album = Album.objects.create(name="A")
        photo = Photo.objects.create(album=album, name="a.jpg", image="x/a.jpg")

        REPO.update_photo(photo.pk, {"description": "Páscoa", "date_taken": None})

        assert REPO.get_photo(photo.pk).description == "Páscoa"  # type: ignore[union-attr]

    def test_photos_without_thumbnail_and_set_thumbnail(self) -> None:
        album = Album.objects.create(name="A")
        bare = Photo.objects.create(album=album, name="a.jpg", image="x/a.jpg")
        Photo.objects.create(album=album, name="b.jpg", image="x/b.jpg", thumbnail="t/b.jpg")

        assert list(REPO.photos_without_thumbnail()) == [(bare.pk, album.pk, "x/a.jpg")]
        REPO.set_thumbnail(bare.pk, "t/a.jpg")
        assert list(REPO.photos_without_thumbnail()) == []
