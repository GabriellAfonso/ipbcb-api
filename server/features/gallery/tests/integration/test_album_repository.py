from datetime import timedelta

import pytest

from core.domain.exceptions import AlbumNotFoundError, DuplicateAlbumNameError
from features.gallery.dtos.gallery_dtos import AlbumCreate
from features.gallery.models.gallery import Album, Photo
from features.gallery.repositories.album_repository import AlbumRepositoryImpl
from features.gallery.tests.fakes import FakeClock

CLOCK = FakeClock()
REPO = AlbumRepositoryImpl(CLOCK)


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


LATER = FakeClock.START + timedelta(days=3)


@pytest.mark.django_db
class TestChangeTracking:
    """specs/014-gallery-trash-sync research R-06."""

    def test_writes_set_updated_at(self) -> None:
        CLOCK.current = FakeClock.START
        album_id = REPO.create(AlbumCreate(name="A"), position=0)
        assert Album.objects.get(pk=album_id).updated_at == FakeClock.START

        CLOCK.current = LATER
        REPO.update(album_id, {"description": "x"})
        assert Album.objects.get(pk=album_id).updated_at == LATER

        CLOCK.current = LATER + timedelta(hours=1)
        REPO.set_cover_name(album_id, "c.jpg")
        assert Album.objects.get(pk=album_id).updated_at == CLOCK.current

    def test_apply_order_touches_only_rows_that_move(self) -> None:
        CLOCK.current = FakeClock.START
        ids = [REPO.create(AlbumCreate(name=n), position=i) for i, n in enumerate("ABC")]
        CLOCK.current = LATER

        REPO.apply_order([ids[1], ids[0], ids[2]])

        stamps = dict(Album.objects.values_list("id", "updated_at"))
        assert (stamps[ids[0]], stamps[ids[1]], stamps[ids[2]]) == (LATER, LATER, FakeClock.START)

    def test_touch_and_touch_photos_of(self) -> None:
        CLOCK.current = FakeClock.START
        album, other = Album.objects.create(name="A"), Album.objects.create(name="B")
        mine = Photo.objects.create(album=album, name="a.jpg", image="x/a.jpg")
        theirs = Photo.objects.create(album=other, name="b.jpg", image="x/b.jpg")
        CLOCK.current = LATER

        REPO.touch([album.pk])
        REPO.touch_photos_of(album.pk)

        assert Album.objects.get(pk=album.pk).updated_at == LATER
        assert Album.objects.get(pk=other.pk).updated_at != LATER
        assert Photo.objects.get(pk=mine.pk).updated_at == LATER
        assert Photo.objects.get(pk=theirs.pk).updated_at != LATER

    def test_live_sibling_named_ignores_trashed(self) -> None:
        parent = Album.objects.create(name="P")
        trashed = Album.objects.create(name="Culto", parent=parent)
        Album.all_objects.filter(pk=trashed.pk).update(deleted_at=LATER)
        assert REPO.live_sibling_named("Culto", parent.pk) is None

        live = Album.objects.create(name="Culto", parent=parent)
        assert REPO.live_sibling_named("Culto", parent.pk) == live.pk

    def test_regression_next_position_under_a_trashed_parent_is_refused(self) -> None:
        parent = Album.objects.create(name="P")
        Album.all_objects.filter(pk=parent.pk).update(deleted_at=LATER)

        with pytest.raises(AlbumNotFoundError):
            REPO.next_position(parent.pk)

    def test_reads_ignore_trashed_albums(self) -> None:
        live = Album.objects.create(name="A")
        gone = Album.objects.create(name="B")
        Album.all_objects.filter(pk=gone.pk).update(deleted_at=LATER)

        assert [r.id for r in REPO.list_records()] == [live.pk]
        assert REPO.get_record(gone.pk) is None
        assert not REPO.exists(gone.pk)
