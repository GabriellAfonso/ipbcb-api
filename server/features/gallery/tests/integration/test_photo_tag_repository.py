"""PhotoTagRepositoryImpl and the member filter against the test database
(specs/015-gallery-member-tags research R-04, R-05, R-07, R-08)."""

from datetime import timedelta
from typing import Any

import pytest
from django.apps import apps
from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext

from features.gallery.domain.tag_rules import TagDiff
from features.gallery.models.gallery import Album, Photo
from features.gallery.models.tags import PhotoTag
from features.gallery.repositories.gallery_repository import GalleryRepositoryImpl
from features.gallery.repositories.photo_tag_repository import PhotoTagRepositoryImpl
from features.gallery.tests.fakes import FakeClock

CLOCK = FakeClock()
LATER = FakeClock.START + timedelta(hours=1)


class Rows:
    """Album A with photos p1, p2, p3; members Ana and Bruno; every photo last changed at START."""

    def __init__(self) -> None:
        member = apps.get_model("members", "Member")
        self.album = Album.objects.create(name="A")
        self.p1, self.p2, self.p3 = (
            Photo.objects.create(album=self.album, name=f"{i}.jpg", image=f"x/{i}.jpg", position=i)
            for i in range(3)
        )
        self.ana: Any = member.objects.create(name="Ana")
        self.bruno: Any = member.objects.create(name="Bruno")
        Photo.all_objects.update(updated_at=FakeClock.START)

    def tag(self, photo: Photo, *members: Any) -> None:
        PhotoTag.objects.bulk_create([PhotoTag(photo=photo, member=m) for m in members])

    def changed(self) -> set[int]:
        rows = Photo.all_objects.filter(updated_at__gt=FakeClock.START)
        return set(rows.values_list("id", flat=True))


def _repo() -> PhotoTagRepositoryImpl:
    return PhotoTagRepositoryImpl(FakeClock(LATER))


@pytest.mark.django_db
class TestWrites:
    def test_lock_returns_live_photos_only(self) -> None:
        rows = Rows()
        Photo.all_objects.filter(pk=rows.p2.pk).update(deleted_at=LATER)

        assert _repo().lock_live_photos([rows.p3.pk, rows.p2.pk, rows.p1.pk, 999]) == [
            rows.p1.pk,
            rows.p3.pk,
        ]

    def test_current_tags_includes_untagged_photos(self) -> None:
        rows = Rows()
        rows.tag(rows.p1, rows.ana, rows.bruno)

        assert _repo().current_tags([rows.p1.pk, rows.p2.pk]) == {
            rows.p1.pk: {rows.ana.pk, rows.bruno.pk},
            rows.p2.pk: set(),
        }

    def test_write_diff_changes_pairs_and_marks_only_those_photos(self) -> None:
        rows = Rows()
        rows.tag(rows.p1, rows.ana)
        diff = TagDiff(added={rows.p2.pk: [rows.ana.pk]}, removed={rows.p1.pk: [rows.ana.pk]})

        _repo().write_diff(diff, None)

        assert set(PhotoTag.objects.values_list("photo_id", "member_id")) == {
            (rows.p2.pk, rows.ana.pk)
        }
        assert rows.changed() == {rows.p1.pk, rows.p2.pk}

    def test_empty_diff_touches_nothing(self) -> None:
        rows = Rows()

        _repo().write_diff(TagDiff(), None)

        assert rows.changed() == set()


@pytest.mark.django_db
class TestTaggedMembers:
    def test_counts_live_photos_only(self) -> None:
        rows = Rows()
        rows.tag(rows.p1, rows.ana, rows.bruno)
        rows.tag(rows.p2, rows.ana)
        rows.tag(rows.p3, rows.bruno)
        Photo.all_objects.filter(pk=rows.p3.pk).update(deleted_at=LATER)

        members = _repo().tagged_members()

        assert [(m.name, m.photo_count) for m in members] == [("Ana", 2), ("Bruno", 1)]

    def test_member_whose_photos_are_all_trashed_is_absent(self) -> None:
        rows = Rows()
        rows.tag(rows.p3, rows.bruno)
        Photo.all_objects.filter(pk=rows.p3.pk).update(deleted_at=LATER)

        assert _repo().tagged_members() == []


@pytest.mark.django_db
class TestMemberChanges:
    def test_rename_marks_the_member_s_live_photos(self) -> None:
        rows = Rows()
        rows.tag(rows.p1, rows.ana)
        rows.tag(rows.p2, rows.ana)
        Photo.all_objects.filter(pk=rows.p2.pk).update(deleted_at=LATER)

        _repo().touch_photos_if_renamed(rows.ana.pk, "Ana Maria")

        assert rows.changed() == {rows.p1.pk}

    def test_same_name_marks_nothing(self) -> None:
        rows = Rows()
        rows.tag(rows.p1, rows.ana)

        _repo().touch_photos_if_renamed(rows.ana.pk, "Ana")

        assert rows.changed() == set()

    def test_untagged_member_costs_one_query(self) -> None:
        rows = Rows()

        with CaptureQueriesContext(connection) as queries:
            _repo().touch_photos_if_renamed(rows.bruno.pk, "Bruno Lima")

        assert len(queries) == 1
        assert rows.changed() == set()

    def test_delete_marks_before_the_tags_go(self) -> None:
        rows = Rows()
        rows.tag(rows.p1, rows.ana)

        _repo().touch_photos_of_member(rows.ana.pk)

        assert rows.changed() == {rows.p1.pk}


@pytest.mark.django_db
class TestFilterAndMembers:
    def test_and_filter_and_members_by_name(self) -> None:
        rows = Rows()
        rows.tag(rows.p1, rows.bruno, rows.ana)
        rows.tag(rows.p2, rows.ana)
        repository = GalleryRepositoryImpl(CLOCK)

        both = repository.list_all_photos(frozenset({rows.ana.pk, rows.bruno.pk}))
        ana = repository.list_photos_by_album(rows.album.pk, frozenset({rows.ana.pk}))
        unknown = repository.list_all_photos(frozenset({999_999}))

        assert [p.id for p in both] == [rows.p1.pk]
        assert [m.name for m in both[0].members] == ["Ana", "Bruno"]
        assert [p.id for p in ana] == [rows.p1.pk, rows.p2.pk]
        assert unknown == []

    def test_members_of_every_photo_in_two_queries(self) -> None:
        rows = Rows()
        rows.tag(rows.p1, rows.ana)
        rows.tag(rows.p2, rows.ana, rows.bruno)

        with CaptureQueriesContext(connection) as queries:
            photos = GalleryRepositoryImpl(CLOCK).list_all_photos()

        assert len(queries) == 2
        assert [len(p.members) for p in photos] == [1, 2, 0]

    def test_a_pair_is_tagged_at_most_once(self) -> None:
        rows = Rows()
        rows.tag(rows.p1, rows.ana)

        with pytest.raises(IntegrityError), transaction.atomic():
            rows.tag(rows.p1, rows.ana)

    def test_deleting_a_member_or_a_photo_row_removes_its_tags(self) -> None:
        rows = Rows()
        rows.tag(rows.p1, rows.ana, rows.bruno)
        rows.tag(rows.p2, rows.ana)

        rows.ana.delete()
        Photo.all_objects.filter(pk=rows.p1.pk).delete()

        assert list(PhotoTag.objects.values_list("photo_id", "member_id")) == []
