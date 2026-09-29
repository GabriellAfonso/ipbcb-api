"""Sibling-unique album names are enforced by the database, roots included
(specs/013-gallery-write-api FR-005, research R-01)."""

import pytest
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from features.gallery.models.gallery import Album


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
