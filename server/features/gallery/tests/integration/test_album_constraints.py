"""Sibling-unique album names are enforced by the database, roots included
(specs/013-gallery-write-api FR-005, research R-01)."""

import pytest
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.utils import timezone

from features.gallery.models.gallery import Album, Photo


@pytest.mark.django_db
class TestAlbumNameConstraints:
    def test_regression_two_roots_cannot_share_a_name(self) -> None:
        Album.objects.create(name="Retiros")

        with pytest.raises(IntegrityError), transaction.atomic():
            Album.objects.create(name="Retiros")

    def test_same_name_under_different_parents_is_allowed(self) -> None:
        camps = Album.objects.create(name="Acampamentos")
        retreats = Album.objects.create(name="Retiros")

        Album.objects.create(name="2025", parent=camps)
        Album.objects.create(name="2025", parent=retreats)

        assert Album.objects.filter(name="2025").count() == 2

    def test_same_name_twice_under_one_parent_is_refused(self) -> None:
        parent = Album.objects.create(name="Retiros")
        Album.objects.create(name="2025", parent=parent)

        with pytest.raises(IntegrityError), transaction.atomic():
            Album.objects.create(name="2025", parent=parent)

    def test_root_and_child_may_share_a_name(self) -> None:
        root = Album.objects.create(name="2025")

        Album.objects.create(name="2025", parent=root)

        assert Album.objects.filter(name="2025").count() == 2

    def test_full_clean_reports_the_root_duplicate(self) -> None:
        # The Django admin form runs validate_constraints() through full_clean().
        Album.objects.create(name="Retiros")

        with pytest.raises(DjangoValidationError):
            Album(name="Retiros").full_clean()


@pytest.mark.django_db
class TestAlbumParentProtect:
    def test_album_with_a_child_cannot_be_deleted(self) -> None:
        parent = Album.objects.create(name="Retiros")
        Album.objects.create(name="2025", parent=parent)

        with pytest.raises(ProtectedError):
            parent.delete()


def _trashed(album: Album) -> Album:
    Album.all_objects.filter(pk=album.pk).update(deleted_at=timezone.now())
    return album


@pytest.mark.django_db
class TestTrashedAlbumsDoNotHoldTheirName:
    """specs/014-gallery-trash-sync FR-010: a trashed "Culto" never blocks a new "Culto"."""

    def test_regression_root_name_is_free_after_trash(self) -> None:
        _trashed(Album.objects.create(name="Culto"))

        Album.objects.create(name="Culto")

        assert Album.all_objects.filter(name="Culto").count() == 2

    def test_regression_child_name_is_free_after_trash(self) -> None:
        parent = Album.objects.create(name="Retiros")
        _trashed(Album.objects.create(name="Culto", parent=parent))

        Album.objects.create(name="Culto", parent=parent)

        assert Album.all_objects.filter(name="Culto", parent=parent).count() == 2

    def test_two_live_siblings_still_conflict(self) -> None:
        parent = Album.objects.create(name="Retiros")
        _trashed(Album.objects.create(name="Culto", parent=parent))
        Album.objects.create(name="Culto", parent=parent)

        with pytest.raises(IntegrityError), transaction.atomic():
            Album.objects.create(name="Culto", parent=parent)


@pytest.mark.django_db
class TestManagers:
    def test_default_manager_hides_trashed_rows_and_all_objects_keeps_them(self) -> None:
        live = Album.objects.create(name="Vivo")
        trashed = _trashed(Album.objects.create(name="Lixeira"))
        photo = Photo.objects.create(album=live, name="a.jpg", image="gallery/1/a.jpg")
        Photo.all_objects.filter(pk=photo.pk).update(deleted_at=timezone.now())

        assert list(Album.objects.values_list("pk", flat=True)) == [live.pk]
        assert set(Album.all_objects.values_list("pk", flat=True)) == {live.pk, trashed.pk}
        assert not Photo.objects.exists()
        assert Photo.all_objects.count() == 1


@pytest.mark.django_db
class TestPhotoAlbumProtect:
    def test_album_with_a_photo_row_cannot_be_deleted(self) -> None:
        album = Album.objects.create(name="Retiros")
        Photo.objects.create(album=album, name="a.jpg", image="gallery/1/a.jpg")

        with pytest.raises(ProtectedError):
            album.delete()
