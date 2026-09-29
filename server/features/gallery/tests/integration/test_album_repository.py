import pytest

from core.domain.exceptions import DuplicateAlbumNameError
from features.gallery.dtos.gallery_dtos import AlbumCreate
from features.gallery.models.gallery import Album, Photo
from features.gallery.repositories.album_repository import AlbumRepositoryImpl

REPO = AlbumRepositoryImpl()


@pytest.mark.django_db
class TestDuplicateTranslation:
    def test_root_duplicate_from_the_constraint(self) -> None:
        REPO.create(AlbumCreate(name="Retiros"), position=0)

        with pytest.raises(DuplicateAlbumNameError):
            REPO.create(AlbumCreate(name="Retiros"), position=1)

    def test_child_duplicate_on_update(self) -> None:
        parent = Album.objects.create(name="Retiros")
        Album.objects.create(name="2025", parent=parent)
        other = Album.objects.create(name="2026", parent=parent)

        with pytest.raises(DuplicateAlbumNameError):
            REPO.update(other.pk, {"name": "2025", "parent_id": parent.pk})


@pytest.mark.django_db
class TestQueries:
    def test_records_carry_every_field(self) -> None:
        album = Album.objects.create(name="Retiros", cover_image="gallery/covers/1/c.jpg")

        record = REPO.get_record(album.pk)

        assert record is not None
        assert (record.name, record.parent_id, record.cover_name) == (
            "Retiros",
            None,
            "gallery/covers/1/c.jpg",
        )
        assert REPO.get_record(999) is None
        assert [r.id for r in REPO.list_records()] == [album.pk]

    def test_parent_map(self) -> None:
        root = Album.objects.create(name="A")
        child = Album.objects.create(name="B", parent=root)

        assert REPO.parent_map(lock=False) == {root.pk: None, child.pk: root.pk}

    def test_sibling_name_taken_excludes_the_album_itself(self) -> None:
        album = Album.objects.create(name="Retiros")

        assert REPO.sibling_name_taken("Retiros", None, exclude_id=None)
        assert not REPO.sibling_name_taken("Retiros", None, exclude_id=album.pk)
        assert not REPO.sibling_name_taken("Retiros", album.pk, exclude_id=None)

    def test_next_position_and_child_ids(self) -> None:
        root = Album.objects.create(name="A", position=3)
        Album.objects.create(name="C", parent=root, position=1)
        Album.objects.create(name="B", parent=root, position=0)

        assert REPO.next_position(None) == 4
        assert REPO.next_position(root.pk) == 2
        assert [Album.objects.get(pk=i).name for i in REPO.child_ids(root.pk)] == ["B", "C"]

    def test_next_position_of_an_empty_parent(self) -> None:
        assert REPO.next_position(None) == 0

    def test_apply_order(self) -> None:
        first, second = Album.objects.create(name="A"), Album.objects.create(name="B")

        REPO.apply_order([second.pk, first.pk])

        assert REPO.child_ids(None) == [second.pk, first.pk]

    def test_has_photos(self) -> None:
        album = Album.objects.create(name="A")
        assert not REPO.has_photos(album.pk)

        Photo.objects.create(album=album, name="a.jpg", image="x/a.jpg")
        assert REPO.has_photos(album.pk)


@pytest.mark.django_db
class TestCover:
    def test_set_and_clear(self) -> None:
        album = Album.objects.create(name="A")

        REPO.set_cover_name(album.pk, "gallery/covers/1/c.jpg")
        assert Album.objects.get(pk=album.pk).cover_image.name == "gallery/covers/1/c.jpg"
        REPO.set_cover_name(album.pk, None)
        assert Album.objects.get(pk=album.pk).cover_image.name == ""

    def test_set_if_absent_does_not_overwrite(self) -> None:
        album = Album.objects.create(name="A")

        assert REPO.set_cover_name_if_absent(album.pk, "first.jpg")
        assert not REPO.set_cover_name_if_absent(album.pk, "second.jpg")
        assert Album.objects.get(pk=album.pk).cover_image.name == "first.jpg"
